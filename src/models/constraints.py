from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering
from typing import Iterable


_COMPARATOR_RE = re.compile(r"^(<=|>=|<|>|==|=)?\s*([A-Za-z0-9_.+\-]+)$")


@total_ordering
@dataclass(frozen=True)
class Version:
    """Small semver-like ordering helper for registry fixtures and demos."""

    raw: str

    @property
    def parts(self) -> tuple[int, int, int, str]:
        main, _, suffix = self.raw.partition("-")
        numeric_parts: list[int] = []
        for part in main.split("."):
            match = re.match(r"\d+", part)
            numeric_parts.append(int(match.group(0)) if match else 0)
        while len(numeric_parts) < 3:
            numeric_parts.append(0)
        return numeric_parts[0], numeric_parts[1], numeric_parts[2], suffix

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self.parts < other.parts

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self.parts == other.parts


@dataclass(frozen=True)
class VersionRange:
    """Parse a pragmatic subset of npm/Poetry version constraints."""

    raw: str = "*"

    def allows(self, version: str) -> bool:
        raw = (self.raw or "*").strip()
        if raw in {"", "*", "latest"}:
            return True

        alternatives = [part.strip() for part in raw.split("||")]
        return any(self._allows_all_constraints(alt, version) for alt in alternatives)

    def _allows_all_constraints(self, raw: str, version: str) -> bool:
        constraints = self._expand_constraint(raw)
        candidate = Version(version)
        for operator, boundary in constraints:
            required = Version(boundary)
            if operator in {"=", "=="} and candidate != required:
                return False
            if operator == ">=" and candidate < required:
                return False
            if operator == ">" and (candidate < required or candidate == required):
                return False
            if operator == "<=" and required < candidate:
                return False
            if operator == "<" and (required < candidate or candidate == required):
                return False
        return True

    def _expand_constraint(self, raw: str) -> list[tuple[str, str]]:
        raw = raw.strip()
        if raw in {"", "*", "latest"}:
            return []
        if raw.startswith("^"):
            return self._caret(raw[1:].strip())
        if raw.startswith("~"):
            return self._tilde(raw[1:].strip())

        pieces = [piece for piece in re.split(r"[,\s]+", raw) if piece]
        expanded: list[tuple[str, str]] = []
        for piece in pieces:
            match = _COMPARATOR_RE.match(piece)
            if not match:
                raise ValueError(f"Unsupported version constraint: {raw!r}")
            operator = match.group(1) or "=="
            expanded.append((operator, match.group(2)))
        return expanded

    def _caret(self, version: str) -> list[tuple[str, str]]:
        major, minor, patch, _ = Version(version).parts
        if major > 0:
            upper = f"{major + 1}.0.0"
        elif minor > 0:
            upper = f"0.{minor + 1}.0"
        else:
            upper = f"0.0.{patch + 1}"
        return [
            (">=", version),
            ("<", upper),
        ]

    def _tilde(self, version: str) -> list[tuple[str, str]]:
        major, minor, _, _ = Version(version).parts
        return [
            (">=", version),
            ("<", f"{major}.{minor + 1}.0"),
        ]

    @classmethod
    def any(cls) -> "VersionRange":
        return cls("*")


@dataclass(frozen=True)
class Term:
    """A SAT literal for a concrete package version."""

    package: str
    version: str
    is_positive: bool = True

    @property
    def atom(self) -> str:
        return f"{self.package}=={self.version}"

    def negate(self) -> "Term":
        return Term(self.package, self.version, not self.is_positive)

    def __str__(self) -> str:
        prefix = "" if self.is_positive else "not "
        return f"{prefix}{self.atom}"


@dataclass(frozen=True)
class Incompatibility:
    """A CNF clause generated from package constraints or learned conflicts."""

    terms: tuple[Term, ...]
    cause: str = "derived"

    def __init__(self, terms: Iterable[Term], cause: str = "derived") -> None:
        object.__setattr__(self, "terms", tuple(terms))
        object.__setattr__(self, "cause", cause)

    def __str__(self) -> str:
        body = " OR ".join(str(term) for term in self.terms) or "<empty>"
        return f"{body} ({self.cause})"
