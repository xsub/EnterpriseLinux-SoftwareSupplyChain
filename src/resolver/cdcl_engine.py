from __future__ import annotations

from dataclasses import dataclass

from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.models.constraints import Incompatibility, Term, Version, VersionRange
from src.resolver.registry_mock import RegistryMock


class ResolutionError(RuntimeError):
    """Raised when no version assignment can satisfy all dependency constraints."""


@dataclass(frozen=True)
class _TrailEntry:
    term: Term
    level: int
    reason: Incompatibility | None


class CDCLResolver:
    """Small PubGrub/CDCL-inspired dependency resolver.

    The implementation encodes dependency metadata as CNF clauses, performs unit
    propagation, chooses package versions only when an active dependency clause
    requires a decision, and learns unary blocking clauses from conflicts.
    """

    def __init__(self, registry: RegistryMock) -> None:
        self.registry = registry
        self.incompatibilities: set[Incompatibility] = set()
        self.partial_solution: list[Term] = []

        self._clauses: list[Incompatibility] = []
        self._variables: dict[str, Term] = {}
        self._assignments: dict[str, bool] = {}
        self._reasons: dict[str, Incompatibility | None] = {}
        self._levels: dict[str, int] = {}
        self._trail: list[_TrailEntry] = []
        self._decision_level = 0

    def solve(self, root_package_name: str, root_version: str) -> CSRDependencyGraph:
        self._reset()
        self._encode_registry(root_package_name, root_version)

        while True:
            conflict = self._unit_propagation()

            if conflict is not None:
                learned_clause = self._analyze_conflict(conflict)
                if learned_clause is None:
                    raise ResolutionError(self._format_conflict(conflict))
                self.incompatibilities.add(learned_clause)
                self._clauses.append(learned_clause)
                self._backtrack_to_clause(learned_clause)
                continue

            next_term = self._decide_next_package()
            if next_term is None:
                break

            self._decision_level += 1
            self._assign(next_term, reason=None)

        self.partial_solution = self._selected_terms()
        return self._build_resolved_graph()

    def _reset(self) -> None:
        self.incompatibilities = set()
        self.partial_solution = []
        self._clauses = []
        self._variables = {}
        self._assignments = {}
        self._reasons = {}
        self._levels = {}
        self._trail = []
        self._decision_level = 0

    def _encode_registry(self, root_package_name: str, root_version: str) -> None:
        for package_name in self.registry.package_names():
            for package in self.registry.versions(package_name):
                self._register_variable(Term(package.name, package.version))

        root_candidates = self.registry.matching_versions(root_package_name, root_version)
        if not root_candidates:
            raise ResolutionError(f"No versions of {root_package_name!r} match {root_version!r}")

        self._add_clause(
            [Term(root_package_name, candidate.version) for candidate in root_candidates],
            cause=f"root requires {root_package_name} {root_version}",
        )

        for package_name in self.registry.package_names():
            versions = self.registry.versions(package_name)
            for left_index, left in enumerate(versions):
                for right in versions[left_index + 1 :]:
                    self._add_clause(
                        [
                            Term(package_name, left.version, is_positive=False),
                            Term(package_name, right.version, is_positive=False),
                        ],
                        cause=f"only one version of {package_name} can be selected",
                    )

        for package_name in self.registry.package_names():
            for package in self.registry.versions(package_name):
                source_negation = Term(package_name, package.version, is_positive=False)
                for dependency in package.dependencies:
                    matching = self.registry.matching_versions(
                        dependency.name, dependency.constraint
                    )
                    allowed = [Term(dependency.name, candidate.version) for candidate in matching]
                    for term in allowed:
                        self._register_variable(term)

                    self._add_clause(
                        [source_negation, *allowed],
                        cause=(
                            f"{package.identifier} requires "
                            f"{dependency.name} {dependency.constraint}"
                        ),
                    )

    def _register_variable(self, term: Term) -> None:
        self._variables.setdefault(term.atom, Term(term.package, term.version))

    def _add_clause(self, terms: list[Term], cause: str) -> None:
        clause = Incompatibility(terms, cause=cause)
        self.incompatibilities.add(clause)
        self._clauses.append(clause)

    def _unit_propagation(self) -> Incompatibility | None:
        while True:
            changed = False
            for clause in self._clauses:
                status = self._clause_status(clause)
                if status == "satisfied":
                    continue
                if status == "conflict":
                    return clause

                unassigned = [
                    term for term in clause.terms if self._literal_value(term) is None
                ]
                if len(unassigned) == 1:
                    term = unassigned[0]
                    assignment_conflict = self._assign(term, reason=clause)
                    if assignment_conflict is not None:
                        return assignment_conflict
                    changed = True

            if not changed:
                return None

    def _clause_status(self, clause: Incompatibility) -> str:
        values = [self._literal_value(term) for term in clause.terms]
        if any(value is True for value in values):
            return "satisfied"
        if all(value is False for value in values):
            return "conflict"
        return "unresolved"

    def _literal_value(self, term: Term) -> bool | None:
        value = self._assignments.get(term.atom)
        if value is None:
            return None
        return value if term.is_positive else not value

    def _assign(
        self, term: Term, reason: Incompatibility | None
    ) -> Incompatibility | None:
        desired_value = term.is_positive
        current_value = self._assignments.get(term.atom)
        if current_value is not None:
            if current_value == desired_value:
                return None
            return Incompatibility([term], cause=f"contradictory assignment for {term.atom}")

        self._assignments[term.atom] = desired_value
        self._reasons[term.atom] = reason
        self._levels[term.atom] = self._decision_level
        self._trail.append(_TrailEntry(term, self._decision_level, reason))
        return None

    def _decide_next_package(self) -> Term | None:
        for clause in self._clauses:
            if self._clause_status(clause) == "satisfied":
                continue
            negative_terms = [term for term in clause.terms if not term.is_positive]
            if not negative_terms:
                continue
            if not all(self._literal_value(term) is False for term in negative_terms):
                continue

            positive_choices = [
                term
                for term in clause.terms
                if term.is_positive and self._literal_value(term) is None
            ]
            if positive_choices:
                return max(positive_choices, key=lambda term: Version(term.version))

        return None

    def _analyze_conflict(self, conflict: Incompatibility) -> Incompatibility | None:
        decisions = [entry for entry in self._trail if entry.reason is None]
        if not decisions:
            return None

        current_decision = max(decisions, key=lambda entry: entry.level)
        learned_term = current_decision.term.negate()
        return Incompatibility(
            [learned_term],
            cause=f"learned from conflict: {conflict.cause}",
        )

    def _backtrack_to_clause(self, learned_clause: Incompatibility) -> None:
        learned_atoms = {term.atom for term in learned_clause.terms}
        levels = [self._levels[atom] for atom in learned_atoms if atom in self._levels]
        backtrack_level = max(levels, default=self._decision_level) - 1
        backtrack_level = max(backtrack_level, 0)

        retained_trail: list[_TrailEntry] = []
        for entry in self._trail:
            if entry.level <= backtrack_level:
                retained_trail.append(entry)
                continue
            self._assignments.pop(entry.term.atom, None)
            self._reasons.pop(entry.term.atom, None)
            self._levels.pop(entry.term.atom, None)

        self._trail = retained_trail
        self._decision_level = backtrack_level

    def _selected_terms(self) -> list[Term]:
        selected = [
            self._variables[atom]
            for atom, value in self._assignments.items()
            if value and atom in self._variables
        ]
        return sorted(selected, key=lambda term: (term.package, Version(term.version)))

    def _build_resolved_graph(self) -> CSRDependencyGraph:
        graph = CSRDependencyGraph()
        selected_terms = self._selected_terms()
        selected_by_package = {term.package: term for term in selected_terms}

        for term in selected_terms:
            graph.add_vertex(term.atom)

        for source_term in selected_terms:
            package = self.registry.package(source_term.package, source_term.version)
            for dependency in package.dependencies:
                target_term = selected_by_package.get(dependency.name)
                if target_term is None:
                    continue
                if VersionRange(dependency.constraint).allows(target_term.version):
                    graph.add_dependency_edge(source_term.atom, target_term.atom)

        return graph

    def _format_conflict(self, conflict: Incompatibility) -> str:
        assignments = ", ".join(
            f"{atom}={value}" for atom, value in sorted(self._assignments.items())
        )
        return f"Version conflict cannot be resolved: {conflict}. Assignments: {assignments}"
