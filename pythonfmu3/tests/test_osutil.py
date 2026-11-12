import pytest

from pythonfmu3 import osutil


@pytest.mark.parametrize(
    "system, machine, is_64bit, expected",
    [
        ("Darwin", "arm64", True, "aarch64-darwin"),     # Apple Silicon
        ("Darwin", "x86_64", True, "x86_64-darwin"),     # Intel Mac (or Rosetta)
        ("Linux", "x86_64", True, "x86_64-linux"),
        ("Linux", "aarch64", True, "aarch64-linux"),     # Raspberry Pi 4/5, Graviton
        ("Linux", "armv7l", False, "aarch32-linux"),
        ("Windows", "AMD64", True, "x86_64-windows"),
        ("Windows", "AMD64", False, "x86-windows"),      # 32-bit Python on 64-bit Windows
        ("Windows", "ARM64", True, "aarch64-windows"),
    ],
)
def test_fmi3_platform_tuple(monkeypatch, system, machine, is_64bit, expected):
    monkeypatch.setattr(osutil.platform, "system", lambda: system)
    monkeypatch.setattr(osutil.platform, "machine", lambda: machine)
    monkeypatch.setattr(osutil, "_is_64bit", lambda: is_64bit)
    assert osutil.get_platform() == expected
