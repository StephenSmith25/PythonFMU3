"""Several FMUs in one Python process must each run their own model script, even when the
scripts share a module name (two different "model.py") or a module of that name is already
imported. This is the situation in FMPy or a Python co-simulation script."""
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path

import pytest

from pythonfmu3.builder import FmuBuilder
from pythonfmu3.osutil import get_lib_extension, get_platform

pytestmark = pytest.mark.skipif(not FmuBuilder.has_binary(), reason="needs the compiled wrapper")

MODEL = """
from pythonfmu3 import Fmi3Causality, Fmi3Slave, Fmi3Variability, Float64


class {name}(Fmi3Slave):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.time = 0.0
        self.y = 0.0
        self.register_variable(Float64("time", causality=Fmi3Causality.independent,
                                       variability=Fmi3Variability.continuous))
        self.register_variable(Float64("y", causality=Fmi3Causality.output))

    def do_step(self, current_time, step_size):
        self.y = {value}
        self.time = current_time + step_size
        return True
"""

HOST = r"""
import ctypes as C, sys, types
# An unrelated module already imported under the same name as the FMUs' scripts
sys.modules["model"] = types.ModuleType("model")

CB = C.CFUNCTYPE(None, C.c_void_p, C.c_int, C.c_char_p, C.c_char_p)
log = CB(lambda e, s, c, m: print("LOG", m.decode(), file=sys.stderr))

def run(lib_path, resources, vr_y):
    lib = C.CDLL(lib_path)
    lib.fmi3InstantiateCoSimulation.restype = C.c_void_p
    lib.fmi3InstantiateCoSimulation.argtypes = [C.c_char_p] * 3 + [C.c_bool] * 4 + [C.c_void_p, C.c_size_t, C.c_void_p, CB, C.c_void_p]
    lib.fmi3EnterInitializationMode.argtypes = [C.c_void_p, C.c_bool, C.c_double, C.c_double, C.c_bool, C.c_double]
    lib.fmi3ExitInitializationMode.argtypes = [C.c_void_p]
    lib.fmi3DoStep.argtypes = [C.c_void_p, C.c_double, C.c_double, C.c_bool] + [C.POINTER(C.c_bool)] * 3 + [C.POINTER(C.c_double)]
    lib.fmi3GetFloat64.argtypes = [C.c_void_p, C.POINTER(C.c_uint32), C.c_size_t, C.POINTER(C.c_double), C.c_size_t]
    c = lib.fmi3InstantiateCoSimulation(b"i", b"", resources.encode(), False, True, False, False, None, 0, None, log, None)
    assert c, "instantiation failed"
    assert lib.fmi3EnterInitializationMode(c, False, 0, 0, False, 0) == 0
    assert lib.fmi3ExitInitializationMode(c) == 0
    b = [C.c_bool() for _ in range(3)]; last = C.c_double()
    assert lib.fmi3DoStep(c, 0.0, 0.1, True, *[C.byref(x) for x in b], C.byref(last)) == 0
    out = (C.c_double * 1)()
    assert lib.fmi3GetFloat64(c, (C.c_uint32 * 1)(vr_y), 1, out, 1) == 0
    return out[0]

args = sys.argv[1:]
print([run(args[i], args[i + 1], 1) for i in range(0, len(args), 2)])
"""


def build(tmp_path, folder, name, value):
    src = tmp_path / folder
    src.mkdir()
    (src / "model.py").write_text(MODEL.format(name=name, value=value))
    fmu = FmuBuilder.build_FMU(src / "model.py", dest=tmp_path / f"{folder}_out")
    extracted = tmp_path / f"{folder}_fmu"
    with zipfile.ZipFile(fmu) as z:
        z.extractall(extracted)
    lib = extracted / "binaries" / get_platform() / f"{name}.{get_lib_extension()}"
    return [str(lib), str(extracted / "resources")]


def test_fmus_with_the_same_module_name_run_their_own_code(tmp_path):
    first = build(tmp_path, "a", "FirstModel", 1.0)
    second = build(tmp_path, "b", "SecondModel", 2.0)
    proc = subprocess.run([sys.executable, "-c", HOST, *first, *second, *first],
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-3000:]
    assert proc.stdout.strip() == "[1.0, 2.0, 1.0]"
