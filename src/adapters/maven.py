"""Maven dependency:tree text ingestion for Java dependency graphs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.adapters.base import ResolvedProjectGraph
from src.core_graph.sparse_matrix import CSRDependencyGraph

MAVEN_RELATIONSHIP_DEPENDS_ON = 1
MAVEN_RELATIONSHIP_OPTIONAL = 2
MAVEN_RELATIONSHIP_OMITTED = 3
MAVEN_RELATIONSHIP_EXCLUDED = 4


class MavenTreeAdapter:
    """Build resolved CSR graphs from mvn dependency:tree text output."""

    ecosystem = "maven"

    def parse_tree(self, path: Path) -> ResolvedProjectGraph:
        graph = CSRDependencyGraph()
        stack: list[str] = []
        root_identifier: str | None = None

        for raw_line in path.read_text(encoding="utf-8").splitlines():
            parsed = self._parse_line(raw_line)
            if parsed is None:
                continue
            graph.add_vertex(parsed.identifier, metadata=parsed.metadata)
            if root_identifier is None:
                root_identifier = parsed.identifier

            if parsed.depth > 0 and parsed.depth - 1 < len(stack):
                graph.add_dependency_edge(
                    stack[parsed.depth - 1],
                    parsed.identifier,
                    relationship_type=parsed.relationship_type,
                )

            if len(stack) <= parsed.depth:
                stack.extend([""] * (parsed.depth - len(stack) + 1))
            stack[parsed.depth] = parsed.identifier
            del stack[parsed.depth + 1 :]

        if root_identifier is None:
            raise ValueError(f"No Maven coordinates found in dependency tree: {path}")

        return ResolvedProjectGraph(
            root_identifier=root_identifier,
            graph=graph,
            ecosystem=self.ecosystem,
        )

    def _parse_line(self, raw_line: str) -> "_MavenCoordinate | None":
        line = raw_line.rstrip()
        if line.startswith("[INFO]"):
            line = line.removeprefix("[INFO]")
            if line.startswith(" "):
                line = line[1:]
        if not line.strip() or line.lstrip().startswith(("[WARNING]", "[ERROR]")):
            return None

        depth = 0
        coordinate_text = line
        marker_index = self._marker_index(line)
        if marker_index is not None:
            depth = marker_index // 3 + 1
            coordinate_text = line[marker_index + 3 :].strip()

        coordinate_text, markers = self._extract_markers(coordinate_text)
        parts = coordinate_text.split(":")
        if len(parts) < 4:
            return None

        group = parts[0]
        artifact = parts[1]
        packaging = parts[2]
        classifier = ""
        if len(parts) == 4:
            version = parts[3]
            scope = ""
        elif len(parts) == 5:
            version = parts[3]
            scope = parts[4]
        else:
            classifier = ":".join(parts[3:-2])
            version = parts[-2]
            scope = parts[-1]

        return _MavenCoordinate(
            depth=depth,
            group=group,
            artifact=artifact,
            packaging=packaging,
            version=version,
            scope=scope,
            classifier=classifier,
            optional=markers["optional"],
            omitted=markers["omitted"],
            omitted_reason=markers["omittedReason"],
            excluded=markers["excluded"],
            excluded_reason=markers["excludedReason"],
        )

    def _marker_index(self, line: str) -> int | None:
        marker_positions = [
            position
            for marker in ("+- ", "\\- ")
            if (position := line.find(marker)) >= 0
        ]
        if not marker_positions:
            return None
        return min(marker_positions)

    def _extract_markers(self, coordinate_text: str) -> tuple[str, dict[str, str]]:
        markers = {
            "optional": "",
            "omitted": "",
            "omittedReason": "",
            "excluded": "",
            "excludedReason": "",
        }
        text = coordinate_text.strip()
        if text.startswith("(") and text.endswith(")"):
            text = text[1:-1].strip()

        for suffix, key in (
            (" (optional)", "optional"),
            (" (excluded)", "excluded"),
        ):
            if text.endswith(suffix):
                markers[key] = "true"
                text = text[: -len(suffix)].strip()

        for separator, key in (
            (" - omitted for ", "omitted"),
            (" - excluded by ", "excluded"),
        ):
            if separator in text:
                text, reason = text.split(separator, 1)
                markers[key] = "true"
                reason_key = "omittedReason" if key == "omitted" else "excludedReason"
                markers[reason_key] = reason.strip()
                break

        return text, markers


@dataclass(frozen=True)
class _MavenCoordinate:
    depth: int
    group: str
    artifact: str
    packaging: str
    version: str
    scope: str
    classifier: str = ""
    optional: str = ""
    omitted: str = ""
    omitted_reason: str = ""
    excluded: str = ""
    excluded_reason: str = ""

    @property
    def relationship_type(self) -> int:
        if self.excluded:
            return MAVEN_RELATIONSHIP_EXCLUDED
        if self.omitted:
            return MAVEN_RELATIONSHIP_OMITTED
        if self.optional:
            return MAVEN_RELATIONSHIP_OPTIONAL
        return MAVEN_RELATIONSHIP_DEPENDS_ON

    @property
    def identifier(self) -> str:
        name = f"{self.group}:{self.artifact}"
        if self.packaging != "jar":
            name = f"{name}:{self.packaging}"
        if self.classifier:
            name = f"{name}:{self.classifier}"
        return f"{name}=={self.version}"

    @property
    def coordinate(self) -> str:
        coordinate_parts = [self.group, self.artifact, self.packaging]
        if self.classifier:
            coordinate_parts.append(self.classifier)
        coordinate_parts.append(self.version)
        if self.scope:
            coordinate_parts.append(self.scope)
        return ":".join(coordinate_parts)

    @property
    def metadata(self) -> dict[str, str]:
        metadata = {
            "ecosystem": "maven",
            "source": "maven-dependency-tree",
            "group": self.group,
            "artifact": self.artifact,
            "packaging": self.packaging,
            "coordinate": self.coordinate,
        }
        if self.scope:
            metadata["scope"] = self.scope
        if self.classifier:
            metadata["classifier"] = self.classifier
        if self.optional:
            metadata["optional"] = self.optional
        if self.omitted:
            metadata["omitted"] = self.omitted
        if self.omitted_reason:
            metadata["omittedReason"] = self.omitted_reason
        if self.excluded:
            metadata["excluded"] = self.excluded
        if self.excluded_reason:
            metadata["excludedReason"] = self.excluded_reason
        return metadata
