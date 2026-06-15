"""CSR graph primitives used by resolvers, adapters, and exporters."""

from src.core_graph.sparse_matrix import CSRDependencyGraph, FrozenCSRGraph

__all__ = ["CSRDependencyGraph", "FrozenCSRGraph"]
