"""CSR graph tests for row pointers, neighbor traversal, and duplicate edges."""

import numpy as np

from src.core_graph.sparse_matrix import CSRDependencyGraph


def test_csr_graph_materializes_neighbors_in_row_order() -> None:
    graph = CSRDependencyGraph()

    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")
    graph.add_dependency_edge("app==1.0.0", "tool==2.0.0")
    graph.add_dependency_edge("lib==1.0.0", "base==1.0.0")

    assert graph.get_dependencies("app==1.0.0") == ["lib==1.0.0", "tool==2.0.0"]
    assert graph.get_dependencies("lib==1.0.0") == ["base==1.0.0"]
    assert graph.get_dependencies("missing==0.0.0") == []
    assert graph.row_pointers.tolist() == [0, 2, 3, 3, 3]
    assert graph.column_indices.tolist() == [1, 2, 3]
    assert graph.values.tolist() == [1, 1, 1]
    assert graph.reverse_row_pointers.tolist() == [0, 0, 1, 2, 3]
    assert graph.reverse_column_indices.tolist() == [0, 0, 1]
    assert graph.reverse_values.tolist() == [1, 1, 1]


def test_csr_graph_materializes_numpy_int32_contiguous_arrays() -> None:
    graph = CSRDependencyGraph()

    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")
    graph.add_dependency_edge("app==1.0.0", "tool==2.0.0", relationship_type=7)

    assert graph.get_dependencies("app==1.0.0") == ["lib==1.0.0", "tool==2.0.0"]
    for array in (
        graph.values,
        graph.column_indices,
        graph.row_pointers,
        graph.reverse_values,
        graph.reverse_column_indices,
        graph.reverse_row_pointers,
    ):
        assert isinstance(array, np.ndarray)
        assert array.dtype == np.int32
        assert array.flags.c_contiguous
    assert graph.storage_profile() == {
        "cContiguous": True,
        "columnIndicesBytes": 8,
        "dtype": "int32",
        "layout": "numpy.int32.c_contiguous",
        "rowPointersBytes": 16,
        "reverseColumnIndicesBytes": 8,
        "reverseRowPointersBytes": 16,
        "reverseValuesBytes": 8,
        "totalBytes": 64,
        "valuesBytes": 8,
    }


def test_duplicate_edges_do_not_expand_sparse_arrays() -> None:
    graph = CSRDependencyGraph()
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")

    assert list(graph.edges())[0].source == "app==1.0.0"
    assert len(list(graph.edges())) == 1


def test_most_depended_upon_uses_stable_count_then_name_order() -> None:
    graph = CSRDependencyGraph()
    graph.add_dependency_edge("app==1.0.0", "zlib==1.0.0")
    graph.add_dependency_edge("tool==1.0.0", "zlib==1.0.0")
    graph.add_dependency_edge("app==1.0.0", "abase==1.0.0")
    graph.add_dependency_edge("tool==1.0.0", "abase==1.0.0")
    graph.add_dependency_edge("tool==1.0.0", "leaf==1.0.0")

    assert graph.most_depended_upon(limit=3) == [
        ("abase==1.0.0", 2),
        ("zlib==1.0.0", 2),
        ("leaf==1.0.0", 1),
    ]
    assert CSRDependencyGraph().most_depended_upon() == []


def test_csr_graph_traversal_queries() -> None:
    graph = CSRDependencyGraph()
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")
    graph.add_dependency_edge("app==1.0.0", "tool==2.0.0")
    graph.add_dependency_edge("tool==2.0.0", "lib==1.0.0")
    graph.add_dependency_edge("lib==1.0.0", "base==1.0.0")

    assert graph.get_dependents("lib==1.0.0") == ["app==1.0.0", "tool==2.0.0"]
    assert graph.reachable_dependencies("app==1.0.0") == [
        "lib==1.0.0",
        "tool==2.0.0",
        "base==1.0.0",
    ]
    assert graph.reachable_dependents("base==1.0.0") == [
        "lib==1.0.0",
        "app==1.0.0",
        "tool==2.0.0",
    ]
    assert graph.shortest_dependency_path("app==1.0.0", "base==1.0.0") == [
        "app==1.0.0",
        "lib==1.0.0",
        "base==1.0.0",
    ]
    assert graph.most_depended_upon(limit=2) == [
        ("lib==1.0.0", 2),
        ("base==1.0.0", 1),
    ]


def test_csr_graph_int_native_traversal_queries() -> None:
    graph = CSRDependencyGraph()
    app = graph.add_vertex("app==1.0.0")
    lib = graph.add_vertex("lib==1.0.0")
    tool = graph.add_vertex("tool==2.0.0")
    base = graph.add_vertex("base==1.0.0")
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")
    graph.add_dependency_edge("app==1.0.0", "tool==2.0.0")
    graph.add_dependency_edge("tool==2.0.0", "lib==1.0.0")
    graph.add_dependency_edge("lib==1.0.0", "base==1.0.0")

    assert graph.get_dependency_ids(app).tolist() == [lib, tool]
    assert graph.get_dependent_ids(lib).tolist() == [app, tool]
    assert graph.get_dependency_ids(999).tolist() == []
    assert graph.get_dependent_ids(999).tolist() == []
    assert graph.reachable_dependency_ids(app) == [lib, tool, base]
    assert graph.reachable_dependent_ids(base) == [lib, app, tool]
    assert graph.shortest_dependency_path_ids(app, base) == [app, lib, base]
    assert graph.shortest_dependency_path_ids(base, app, reverse=True) == [
        base,
        lib,
        app,
    ]
    assert graph.shortest_dependency_path_ids(999, base) == []
