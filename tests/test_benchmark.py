"""Synthetic benchmark tests for CSR graph traversal."""

from src.benchmark import run_synthetic_benchmark


def test_synthetic_benchmark_reports_graph_shape_and_timings() -> None:
    payload = run_synthetic_benchmark(nodes=6, fanout=2)

    assert payload["schema"] == "edgp.benchmark.v1"
    assert payload["parameters"] == {"nodes": 6, "fanout": 2}
    assert payload["stats"] == {
        "nodes": 6,
        "edges": 9,
        "reachableFromRoot": 5,
        "reverseReachableFromTail": 5,
    }
    assert payload["timingsMs"]["build"] >= 0
    assert payload["timingsMs"]["reachable"] >= 0
    assert payload["timingsMs"]["reverseReachable"] >= 0
    assert payload["timingsMs"]["mostDependedUpon"] >= 0
    assert payload["storage"]["layout"] == "numpy.int32.c_contiguous"
    assert payload["storage"]["dtype"] == "int32"
    assert payload["storage"]["cContiguous"] is True
    assert payload["storage"]["reverseColumnIndicesBytes"] == payload["storage"][
        "columnIndicesBytes"
    ]
