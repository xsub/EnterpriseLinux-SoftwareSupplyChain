"""DOT graph ingestion for RPM universe and simple dependency graph inputs."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from src.adapters.base import ResolvedProjectGraph
from src.core_graph.sparse_matrix import CSRDependencyGraph

_EDGE_RE = re.compile(r"(?P<source>.+?)\s*->\s*(?P<target>.+)")
_TOKEN_RE = re.compile(r'"([^"]+)"|([A-Za-z0-9_@./:+-]+)')


class DotAdapter:
    """Parse a practical subset of directed DOT dependency graphs."""

    ecosystem = "rpm"

    def parse_graph(self, path: Path, ecosystem: str | None = None) -> ResolvedProjectGraph:
        return self.parse_text(path.read_text(encoding="utf-8"), ecosystem=ecosystem)

    def parse_text(
        self,
        dot_text: str,
        ecosystem: str | None = None,
    ) -> ResolvedProjectGraph:
        ecosystem = ecosystem or self.ecosystem
        graph = CSRDependencyGraph()
        first_source: str | None = None

        for source, targets in self._iter_edges(dot_text):
            source_id = self._package_id(source)
            graph.add_vertex(source_id, metadata={"ecosystem": ecosystem})
            if first_source is None:
                first_source = source_id
            for target in targets:
                target_id = self._package_id(target)
                graph.add_vertex(target_id, metadata={"ecosystem": ecosystem})
                graph.add_dependency_edge(source_id, target_id)

        return ResolvedProjectGraph(
            root_identifier=first_source or "dot-graph",
            graph=graph,
            ecosystem=ecosystem,
        )

    def _iter_edges(self, dot_text: str) -> Iterable[tuple[str, tuple[str, ...]]]:
        lines = iter(dot_text.splitlines())
        for raw_line in lines:
            line = self._clean_line(raw_line)
            if not line or line in {"digraph {", "digraph packages {", "}"}:
                continue

            block_lines: list[str] = []
            if "->" in line and "{" in line and "}" not in line:
                while True:
                    try:
                        block_line = next(lines)
                    except StopIteration:
                        break
                    if "}" in block_line:
                        break
                    block_lines.append(block_line)
                line = f"{line} {' '.join(block_lines)} }}"

            match = _EDGE_RE.search(line.rstrip(";"))
            if match is None:
                continue

            source_tokens = self._tokens(match.group("source"))
            target_tokens = self._tokens(match.group("target").strip("{} "))
            if not source_tokens or not target_tokens:
                continue
            yield source_tokens[0], tuple(target_tokens)

    def _clean_line(self, line: str) -> str:
        return line.split("//", 1)[0].strip()

    def _tokens(self, text: str) -> list[str]:
        return [
            quoted or bare
            for quoted, bare in _TOKEN_RE.findall(text)
            if (quoted or bare) not in {"digraph", "packages"}
        ]

    def _package_id(self, label: str) -> str:
        return label if "==" in label else f"{label}==unknown"
