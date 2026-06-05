import pytest

from src.resolver.cdcl_engine import CDCLResolver, ResolutionError
from src.resolver.registry_mock import RegistryMock


def test_resolver_learns_conflict_and_selects_lower_compatible_version() -> None:
    registry = RegistryMock.from_mapping(
        {
            "app": {
                "1.0.0": {
                    "dependencies": {
                        "addon": ">=1.0.0,<3.0.0",
                        "lib": ">=1.0.0,<3.0.0",
                    }
                },
            },
            "addon": {
                "2.0.0": {"dependencies": {"core": ">=3.0.0,<4.0.0"}},
                "1.0.0": {"dependencies": {"core": ">=1.0.0,<2.0.0"}},
            },
            "lib": {
                "2.0.0": {"dependencies": {"core": ">=2.0.0,<3.0.0"}},
                "1.0.0": {"dependencies": {"core": ">=1.0.0,<2.0.0"}},
            },
            "core": {
                "3.1.0": {"dependencies": {}},
                "2.5.0": {"dependencies": {}},
                "1.5.0": {"dependencies": {}},
            },
        }
    )

    resolver = CDCLResolver(registry)
    graph = resolver.solve("app", "1.0.0")

    assert graph.get_dependencies("app==1.0.0") == ["addon==1.0.0", "lib==1.0.0"]
    assert graph.get_dependencies("addon==1.0.0") == ["core==1.5.0"]
    assert graph.get_dependencies("lib==1.0.0") == ["core==1.5.0"]
    assert any("learned from conflict" in clause.cause for clause in resolver.incompatibilities)


def test_resolver_raises_for_unsatisfiable_constraints() -> None:
    registry = RegistryMock.from_mapping(
        {
            "app": {
                "1.0.0": {"dependencies": {"lib": ">=1.0.0,<2.0.0"}},
            },
            "lib": {
                "1.0.0": {"dependencies": {"core": ">=2.0.0,<3.0.0"}},
            },
            "core": {
                "1.5.0": {"dependencies": {}},
            },
        }
    )

    resolver = CDCLResolver(registry)

    with pytest.raises(ResolutionError):
        resolver.solve("app", "1.0.0")
