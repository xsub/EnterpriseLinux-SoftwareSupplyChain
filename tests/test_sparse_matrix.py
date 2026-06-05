from src.core_graph.sparse_matrix import CSRDependencyGraph


def test_csr_graph_materializes_neighbors_in_row_order() -> None:
    graph = CSRDependencyGraph()

    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")
    graph.add_dependency_edge("app==1.0.0", "tool==2.0.0")
    graph.add_dependency_edge("lib==1.0.0", "base==1.0.0")

    assert graph.get_dependencies("app==1.0.0") == ["lib==1.0.0", "tool==2.0.0"]
    assert graph.get_dependencies("lib==1.0.0") == ["base==1.0.0"]
    assert graph.get_dependencies("missing==0.0.0") == []
    assert graph.row_pointers == [0, 2, 3, 3, 3]
    assert graph.column_indices == [1, 2, 3]


def test_duplicate_edges_do_not_expand_sparse_arrays() -> None:
    graph = CSRDependencyGraph()
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")

    assert list(graph.edges())[0].source == "app==1.0.0"
    assert len(list(graph.edges())) == 1
