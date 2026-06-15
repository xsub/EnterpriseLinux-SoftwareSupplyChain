"""ALBS build metadata ingestion for public AlmaLinux Build System data."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from src.adapters.base import ResolvedProjectGraph
from src.core_graph.sparse_matrix import CSRDependencyGraph

DEFAULT_ALBS_BASE_URL = "https://build.almalinux.org"
ALBS_USER_AGENT = "edgp-albs-adapter/0.1"

REL_ALBS_SOURCE_PACKAGE = 20
REL_ALBS_GIT_REPOSITORY = 21
REL_ALBS_GIT_COMMIT = 22
REL_ALBS_BUILD_TASK = 23
REL_ALBS_BUILD_ENVIRONMENT = 24
REL_ALBS_PRODUCES_ARTIFACT = 25
REL_ALBS_SIGN_TASK = 26
REL_ALBS_TEST_TASK = 27
REL_ALBS_RELEASE = 28


class AlbsBuildAdapter:
    """Build a CSR provenance graph from one ALBS build metadata document."""

    ecosystem = "albs"

    def fetch_build_metadata(
        self,
        build_id: int | str,
        *,
        base_url: str = DEFAULT_ALBS_BASE_URL,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        url = f"{base_url.rstrip('/')}/api/v1/builds/{build_id}/"
        return self.fetch_metadata_url(url, timeout=timeout)

    def fetch_metadata_url(
        self,
        url: str,
        *,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        request = Request(url, headers={"User-Agent": ALBS_USER_AGENT})
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"ALBS build response must be a JSON object: {url}")
        return payload

    def parse_file(
        self,
        path: Path,
        *,
        base_url: str = DEFAULT_ALBS_BASE_URL,
        task_limit: int = 50,
        artifact_limit: int = 200,
        test_task_limit: int = 50,
        include_logs: bool = False,
    ) -> ResolvedProjectGraph:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"ALBS build fixture must be a JSON object: {path}")
        return self.parse_metadata(
            payload,
            base_url=base_url,
            task_limit=task_limit,
            artifact_limit=artifact_limit,
            test_task_limit=test_task_limit,
            include_logs=include_logs,
        )

    def parse_build(
        self,
        build_id: int | str,
        *,
        base_url: str = DEFAULT_ALBS_BASE_URL,
        task_limit: int = 50,
        artifact_limit: int = 200,
        test_task_limit: int = 50,
        include_logs: bool = False,
    ) -> ResolvedProjectGraph:
        return self.parse_metadata(
            self.fetch_build_metadata(build_id, base_url=base_url),
            base_url=base_url,
            task_limit=task_limit,
            artifact_limit=artifact_limit,
            test_task_limit=test_task_limit,
            include_logs=include_logs,
        )

    def parse_url(
        self,
        url: str,
        *,
        base_url: str = DEFAULT_ALBS_BASE_URL,
        task_limit: int = 50,
        artifact_limit: int = 200,
        test_task_limit: int = 50,
        include_logs: bool = False,
    ) -> ResolvedProjectGraph:
        return self.parse_metadata(
            self.fetch_metadata_url(url),
            base_url=base_url,
            task_limit=task_limit,
            artifact_limit=artifact_limit,
            test_task_limit=test_task_limit,
            include_logs=include_logs,
        )

    def parse_metadata(
        self,
        payload: Mapping[str, Any],
        *,
        base_url: str = DEFAULT_ALBS_BASE_URL,
        task_limit: int = 50,
        artifact_limit: int = 200,
        test_task_limit: int = 50,
        include_logs: bool = False,
    ) -> ResolvedProjectGraph:
        graph = CSRDependencyGraph()
        build_id = str(payload.get("id") or payload.get("build_id") or "unknown")
        root_identifier = f"albs-build:{build_id}"
        package_name = _package_name(payload)
        release_id = payload.get("release_id")

        graph.add_vertex(
            root_identifier,
            metadata={
                "ecosystem": self.ecosystem,
                "source": "albs-api",
                "node_type": "albs_build",
                "build_id": build_id,
                "package": package_name,
                "base_url": base_url.rstrip("/"),
                "created_at": payload.get("created_at"),
                "finished_at": payload.get("finished_at"),
                "released": payload.get("released"),
                "release_id": release_id,
                "owner": _owner_username(payload),
            },
        )

        source_id = f"source:{package_name}" if package_name else ""
        if source_id:
            graph.add_vertex(
                source_id,
                metadata={
                    "ecosystem": "rpm",
                    "source": "albs-api",
                    "node_type": "source_package",
                    "package": package_name,
                },
            )
            graph.add_dependency_edge(
                root_identifier,
                source_id,
                REL_ALBS_SOURCE_PACKAGE,
            )

        release_node = ""
        if release_id is not None:
            release_node = f"albs-release:{release_id}"
            graph.add_vertex(
                release_node,
                metadata={
                    "ecosystem": self.ecosystem,
                    "source": "albs-api",
                    "node_type": "release",
                    "release_id": release_id,
                },
            )
            graph.add_dependency_edge(root_identifier, release_node, REL_ALBS_RELEASE)

        artifact_count = 0
        for task in _object_list(payload.get("tasks"))[: max(task_limit, 0)]:
            task_id = _task_node_id(task)
            if not task_id:
                continue
            graph.add_vertex(task_id, metadata=_task_metadata(task, build_id))
            graph.add_dependency_edge(root_identifier, task_id, REL_ALBS_BUILD_TASK)

            ref = task.get("ref") if isinstance(task.get("ref"), dict) else {}
            repo_url = str(ref.get("url") or "")
            if source_id and repo_url:
                repo_id = f"git:{repo_url}"
                graph.add_vertex(
                    repo_id,
                    metadata={
                        "ecosystem": "git",
                        "source": "albs-api",
                        "node_type": "git_repository",
                        "url": repo_url,
                        "package": package_name,
                    },
                )
                graph.add_dependency_edge(
                    source_id,
                    repo_id,
                    REL_ALBS_GIT_REPOSITORY,
                )

            commit_hash = str(ref.get("git_commit_hash") or task.get("alma_commit_cas_hash") or "")
            if commit_hash:
                commit_id = f"git-commit:{commit_hash}"
                graph.add_vertex(
                    commit_id,
                    metadata={
                        "ecosystem": "git",
                        "source": "albs-api",
                        "node_type": "git_commit",
                        "commit": commit_hash,
                        "git_ref": ref.get("git_ref"),
                        "repository": repo_url,
                        "package": package_name,
                    },
                )
                graph.add_dependency_edge(task_id, commit_id, REL_ALBS_GIT_COMMIT)

            env_id = _environment_node_id(task)
            if env_id:
                graph.add_vertex(env_id, metadata=_environment_metadata(task))
                graph.add_dependency_edge(
                    task_id,
                    env_id,
                    REL_ALBS_BUILD_ENVIRONMENT,
                )

            for artifact in _object_list(task.get("artifacts")):
                if artifact_count >= max(artifact_limit, 0):
                    break
                if not include_logs and artifact.get("type") != "rpm":
                    continue
                artifact_id = _artifact_node_id(artifact)
                if not artifact_id:
                    continue
                graph.add_vertex(
                    artifact_id,
                    metadata=_artifact_metadata(artifact, task, build_id),
                )
                graph.add_dependency_edge(
                    task_id,
                    artifact_id,
                    REL_ALBS_PRODUCES_ARTIFACT,
                )
                if release_node and artifact.get("type") == "rpm":
                    graph.add_dependency_edge(artifact_id, release_node, REL_ALBS_RELEASE)
                artifact_count += 1

        for sign_task in _object_list(payload.get("sign_tasks")):
            sign_id = f"albs-sign-task:{sign_task.get('id')}"
            graph.add_vertex(
                sign_id,
                metadata={
                    "ecosystem": self.ecosystem,
                    "source": "albs-api",
                    "node_type": "sign_task",
                    "sign_task_id": sign_task.get("id"),
                    "status": sign_task.get("status"),
                    "started_at": sign_task.get("started_at"),
                    "finished_at": sign_task.get("finished_at"),
                    "stats": _json_metadata(sign_task.get("stats")),
                },
            )
            graph.add_dependency_edge(root_identifier, sign_id, REL_ALBS_SIGN_TASK)
            if release_node:
                graph.add_dependency_edge(sign_id, release_node, REL_ALBS_RELEASE)

        for test_task in _object_list(payload.get("test_tasks"))[: max(test_task_limit, 0)]:
            test_id = f"albs-test-task:{test_task.get('id')}"
            graph.add_vertex(
                test_id,
                metadata={
                    "ecosystem": self.ecosystem,
                    "source": "albs-api",
                    "node_type": "test_task",
                    "test_task_id": test_task.get("id"),
                    "status": test_task.get("status"),
                    "revision": test_task.get("revision"),
                    "performance_stat_count": len(
                        _object_list(test_task.get("performance_stats"))
                    ),
                },
            )
            graph.add_dependency_edge(root_identifier, test_id, REL_ALBS_TEST_TASK)

        return ResolvedProjectGraph(
            root_identifier=root_identifier,
            graph=graph,
            ecosystem=self.ecosystem,
        )


def _package_name(payload: Mapping[str, Any]) -> str:
    explicit = payload.get("package") or payload.get("source_package")
    if explicit:
        return str(explicit)
    for task in _object_list(payload.get("tasks")):
        ref = task.get("ref") if isinstance(task.get("ref"), dict) else {}
        package = _package_from_repository(str(ref.get("url") or ""))
        if package:
            return package
    return "unknown"


def _package_from_repository(repository_url: str) -> str:
    stem = repository_url.rstrip("/").rsplit("/", 1)[-1]
    return stem[:-4] if stem.endswith(".git") else stem


def _owner_username(payload: Mapping[str, Any]) -> str:
    owner = payload.get("owner")
    if isinstance(owner, dict):
        return str(owner.get("username") or owner.get("email") or "")
    return ""


def _task_node_id(task: Mapping[str, Any]) -> str:
    task_id = task.get("id")
    if task_id is None:
        return ""
    arch = str(task.get("arch") or "unknown")
    return f"albs-task:{task_id}:{arch}"


def _task_metadata(task: Mapping[str, Any], build_id: str) -> dict[str, object]:
    platform = task.get("platform") if isinstance(task.get("platform"), dict) else {}
    ref = task.get("ref") if isinstance(task.get("ref"), dict) else {}
    return {
        "ecosystem": "rpm",
        "source": "albs-api",
        "node_type": "build_task",
        "build_id": build_id,
        "task_id": task.get("id"),
        "status": task.get("status"),
        "arch": task.get("arch"),
        "index": task.get("index"),
        "started_at": task.get("started_at"),
        "finished_at": task.get("finished_at"),
        "platform": platform.get("name"),
        "platform_id": platform.get("id"),
        "git_ref": ref.get("git_ref"),
        "alma_commit_cas_hash": task.get("alma_commit_cas_hash"),
        "is_cas_authenticated": task.get("is_cas_authenticated"),
        "is_secure_boot": task.get("is_secure_boot"),
    }


def _environment_node_id(task: Mapping[str, Any]) -> str:
    platform = task.get("platform") if isinstance(task.get("platform"), dict) else {}
    platform_name = str(platform.get("name") or "albs")
    arch = str(task.get("arch") or "")
    return f"buildenv:{platform_name}:{arch}" if arch else ""


def _environment_metadata(task: Mapping[str, Any]) -> dict[str, object]:
    platform = task.get("platform") if isinstance(task.get("platform"), dict) else {}
    return {
        "ecosystem": "rpm",
        "source": "albs-api",
        "node_type": "build_environment",
        "platform": platform.get("name"),
        "platform_id": platform.get("id"),
        "platform_type": platform.get("type"),
        "arch": task.get("arch"),
        "arch_list": ",".join(str(arch) for arch in platform.get("arch_list", [])),
    }


def _artifact_node_id(artifact: Mapping[str, Any]) -> str:
    artifact_id = artifact.get("id")
    name = str(artifact.get("name") or "")
    if artifact_id is None or not name:
        return ""
    if artifact.get("type") == "rpm":
        prefix = "srpm" if name.endswith(".src.rpm") else "rpm"
    else:
        prefix = "build-log"
    return f"{prefix}:{artifact_id}:{name}"


def _artifact_metadata(
    artifact: Mapping[str, Any],
    task: Mapping[str, Any],
    build_id: str,
) -> dict[str, object]:
    name = str(artifact.get("name") or "")
    artifact_type = str(artifact.get("type") or "")
    artifact_kind = "build_log"
    if artifact_type == "rpm":
        artifact_kind = "source_rpm" if name.endswith(".src.rpm") else "binary_rpm"
    return {
        "ecosystem": "rpm" if artifact_type == "rpm" else "albs",
        "source": "albs-api",
        "node_type": artifact_kind,
        "build_id": build_id,
        "task_id": task.get("id"),
        "arch": task.get("arch"),
        "artifact_id": artifact.get("id"),
        "artifact_name": name,
        "artifact_type": artifact_type,
        "href": artifact.get("href"),
        "cas_hash": artifact.get("cas_hash"),
    }


def _object_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _json_metadata(value: object) -> str:
    if value in (None, "", {}, []):
        return ""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
