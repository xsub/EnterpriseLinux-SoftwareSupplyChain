"""Optional accelerator selection tests for CSR traversal backends."""

import pytest

from src.core_graph import accelerators


def test_select_traversal_backend_uses_python_by_default() -> None:
    assert accelerators.select_traversal_backend() == "python"
    assert accelerators.select_traversal_backend("python") == "python"


def test_auto_backend_falls_back_to_python_without_numba(monkeypatch) -> None:
    monkeypatch.setattr(accelerators, "numba_available", lambda: False)

    assert accelerators.select_traversal_backend("auto") == "python"
    assert accelerators.accelerator_profile(requested_backend="auto") == {
        "requestedBackend": "auto",
        "selectedBackend": "python",
        "numba": {
            "available": False,
            "installExtra": ".[fast]",
            "kernels": ["reachable_ids"],
        },
    }


def test_explicit_numba_backend_requires_fast_extra(monkeypatch) -> None:
    monkeypatch.setattr(accelerators, "numba_available", lambda: False)

    with pytest.raises(RuntimeError, match="Numba traversal backend is not available"):
        accelerators.select_traversal_backend("numba")


def test_unknown_backend_is_rejected() -> None:
    with pytest.raises(ValueError, match="backend must be one of"):
        accelerators.select_traversal_backend("unknown")
