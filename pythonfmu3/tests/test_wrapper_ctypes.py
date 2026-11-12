"""Exercise the native wrapper directly through ctypes (no fmpy needed).

Each scenario runs in its own interpreter so a crash in the wrapper fails the test
instead of taking down the test session.
"""
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from pythonfmu3.builder import FmuBuilder

pytestmark = pytest.mark.skipif(
    not FmuBuilder.has_binary() or not sys.platform.startswith("linux"),
    reason="needs the compiled wrapper (ctypes driver is Linux-only)",
)

HERE = Path(__file__).parent
DRIVER = HERE / "fmi3_ctypes_driver.py"


def _extract(script: Path, dest: Path) -> Path:
    fmu = FmuBuilder.build_FMU(script, dest=dest)
    target = dest / fmu.stem
    with zipfile.ZipFile(fmu) as z:
        z.extractall(target)
    return target


@pytest.fixture(scope="module")
def python_slave(tmp_path_factory):
    # A space in the path exercises the resource-path handling
    return _extract(HERE / "slaves/pythonslave.py", tmp_path_factory.mktemp("with space"))


@pytest.fixture(scope="module")
def exception_slave(tmp_path_factory):
    return _extract(HERE / "slaves/PythonSlaveWithException.py", tmp_path_factory.mktemp("exc"))


def _run(scenario: str, fmu_dir: Path):
    proc = subprocess.run(
        [sys.executable, str(DRIVER), scenario, str(fmu_dir)],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"OK {scenario}" in proc.stdout


@pytest.mark.parametrize(
    "scenario",
    ["basic", "bad_vr_type", "too_few_values", "null_logger", "bad_resources", "uri_resources"],
)
def test_wrapper(scenario, python_slave):
    _run(scenario, python_slave)


def test_wrapper_exception_in_step(exception_slave):
    _run("exception_in_step", exception_slave)
