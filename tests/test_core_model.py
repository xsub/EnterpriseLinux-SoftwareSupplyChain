"""Normalized core model and purl generation tests."""

from src.core.model import Package, package_purl


def test_package_purl_generation_for_npm_and_rpm() -> None:
    assert package_purl("npm", "@scope/tool", "2.1.0") == (
        "pkg:npm/%40scope/tool@2.1.0"
    )
    assert package_purl(
        "rpm",
        "bash",
        "5.2.26-6.el10",
        namespace="almalinux",
    ) == "pkg:rpm/almalinux/bash@5.2.26-6.el10"


def test_normalized_package_metadata_uses_purl_identity() -> None:
    metadata = Package(
        ecosystem="npm",
        name="left-pad",
        version="1.3.0",
        source_url="https://registry.npmjs.org/left-pad/-/left-pad-1.3.0.tgz",
        checksum="sha512-demo",
        license="WTFPL",
    ).graph_metadata()

    assert metadata["purl"] == "pkg:npm/left-pad@1.3.0"
    assert metadata["source_url"] == (
        "https://registry.npmjs.org/left-pad/-/left-pad-1.3.0.tgz"
    )
    assert metadata["checksum"] == "sha512-demo"
    assert metadata["license"] == "WTFPL"
