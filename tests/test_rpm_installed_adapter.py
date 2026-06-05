"""Installed RPM adapter tests with a fake command runner."""

from src.adapters.rpm_installed import RPM_QUERY_FORMAT, InstalledRpmAdapter


def test_installed_rpm_adapter_builds_provider_graph() -> None:
    responses = {
        ("rpm", "-qa", "--qf", RPM_QUERY_FORMAT): (
            "bash\t0\t5.2.26-6.el10\tx86_64\tAlmaLinux\tGPL-3.0-or-later\t"
            "bash-5.2.26-6.el10.src.rpm\t1770000001\n"
            "glibc\t0\t2.39-1.el10\tx86_64\tAlmaLinux\tLGPL-2.1-or-later\t"
            "glibc-2.39-1.el10.src.rpm\t1770000002\n"
        ),
        ("rpm", "-q", "--requires", "bash"): (
            "libc.so.6()(64bit)\n"
            "config(bash) = 5.2.26-6.el10\n"
            "rpmlib(CompressedFileNames) <= 3.0.4-1\n"
        ),
        ("rpm", "-q", "--requires", "glibc"): "",
        (
            "rpm",
            "-q",
            "--whatprovides",
            "libc.so.6()(64bit)",
            "--qf",
            RPM_QUERY_FORMAT,
        ): (
            "glibc\t0\t2.39-1.el10\tx86_64\tAlmaLinux\tLGPL-2.1-or-later\t"
            "glibc-2.39-1.el10.src.rpm\t1770000002\n"
        ),
    }

    def fake_runner(args: list[str]) -> str:
        return responses.get(tuple(args), "")

    resolved = InstalledRpmAdapter(command_runner=fake_runner).parse_installed(limit=2)

    assert resolved.root_identifier == "rpm-installed==local"
    assert resolved.graph.get_dependencies("rpm-installed==local") == [
        "bash==5.2.26-6.el10",
        "glibc==2.39-1.el10",
    ]
    assert resolved.graph.get_dependencies("bash==5.2.26-6.el10") == [
        "glibc==2.39-1.el10"
    ]
    assert resolved.graph.get_vertex_metadata("bash==5.2.26-6.el10") == {
        "ecosystem": "rpm",
        "source": "rpmdb",
        "arch": "x86_64",
        "vendor": "AlmaLinux",
        "license": "GPL-3.0-or-later",
        "source_rpm": "bash-5.2.26-6.el10.src.rpm",
        "install_time": "1770000001",
    }
