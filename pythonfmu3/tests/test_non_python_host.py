"""Load a built FMU from a plain C program, i.e. without a Python interpreter in the host.

This is how most FMI importers (OMSimulator, fmusim, Simulink, ...) use an FMU. The
Linux/macOS shim must locate libpython itself in that case.
"""
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import pythonfmu3
from pythonfmu3.builder import FmuBuilder
from pythonfmu3.osutil import get_lib_extension, get_platform

HERE = Path(__file__).parent
CC = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")

pytestmark = [
    pytest.mark.skipif(sys.platform == "win32", reason="the shim is only used on Linux/macOS"),
    pytest.mark.skipif(not FmuBuilder.has_binary(), reason="needs the compiled wrapper"),
    pytest.mark.skipif(CC is None, reason="needs a C compiler"),
]


@pytest.fixture(scope="module")
def host(tmp_path_factory):
    out = tmp_path_factory.mktemp("host") / "fmi3_host"
    include = Path(pythonfmu3.__path__[0]) / "pythonfmu-export" / "src" / "fmi"
    libs = ["-ldl"] if sys.platform.startswith("linux") else []
    subprocess.run([CC, f"-I{include}", str(HERE / "data" / "fmi3_host.c"), "-o", str(out), *libs], check=True)
    return out


@pytest.fixture(scope="module")
def fmu_dir(tmp_path_factory):
    dest = tmp_path_factory.mktemp("fmu")
    fmu = FmuBuilder.build_FMU(HERE / "slaves" / "pythonslave.py", dest=dest)
    target = dest / "extracted"
    with zipfile.ZipFile(fmu) as z:
        z.extractall(target)
    return target


def _run(host, fmu_dir, env):
    library = fmu_dir / "binaries" / get_platform() / f"PythonSlave.{get_lib_extension()}"
    # Minimal environment: nothing Python-related is inherited from the test process
    base = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "TMPDIR")}
    return subprocess.run(
        [str(host), str(library), str(fmu_dir / "resources")],
        capture_output=True, text=True, timeout=120, env={**base, **env},
    )


def test_runs_without_python_host(host, fmu_dir):
    proc = _run(host, fmu_dir, {})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "realOut 1.5" in proc.stdout


def test_library_path_from_environment(host, fmu_dir, tmp_path):
    hints = fmu_dir / "resources" / "pythonfmu_libpython.txt"
    if not hints.exists():
        pytest.skip("building interpreter has no shared libpython")
    library = hints.read_text().splitlines()[0]
    backup = tmp_path / "hints.txt"
    shutil.move(hints, backup)
    try:
        proc = _run(host, fmu_dir, {"PYTHONFMU_PYTHON_LIBRARY": library})
    finally:
        shutil.move(backup, hints)
    assert proc.returncode == 0, proc.stdout + proc.stderr
