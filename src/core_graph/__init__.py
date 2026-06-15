"""CSR graph primitives used by resolvers, adapters, and exporters."""

from src.core_graph.artifacts import (
    load_frozen_csr_artifact,
    write_frozen_csr_artifact,
)
from src.core_graph.parallel import (
    ParallelReachabilityQuery,
    run_parallel_reachability_queries,
)
from src.core_graph.sparse_matrix import CSRDependencyGraph, FrozenCSRGraph

__all__ = [
    "CSRDependencyGraph",
    "FrozenCSRGraph",
    "ParallelReachabilityQuery",
    "load_frozen_csr_artifact",
    "run_parallel_reachability_queries",
    "write_frozen_csr_artifact",
]
