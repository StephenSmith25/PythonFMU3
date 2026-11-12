"""Minimal ctypes FMI 3 co-simulation driver used by test_wrapper_ctypes.py.

usage: python fmi3_ctypes_driver.py <scenario> <extracted_fmu_dir>
"""
import ctypes as C
import sys
from pathlib import Path

scenario, fmu_dir = sys.argv[1], Path(sys.argv[2])
lib_path = next((fmu_dir / "binaries").rglob("*.so"))
lib = C.CDLL(str(lib_path))

LOGCB = C.CFUNCTYPE(None, C.c_void_p, C.c_int, C.c_char_p, C.c_char_p)
logs = []
@LOGCB
def logger(env, status, category, message):
    logs.append((status, (category or b"").decode(), message.decode()))

inst_fn = lib.fmi3InstantiateCoSimulation
inst_fn.restype = C.c_void_p
inst_fn.argtypes = [C.c_char_p, C.c_char_p, C.c_char_p, C.c_bool, C.c_bool, C.c_bool, C.c_bool,
                    C.c_void_p, C.c_size_t, C.c_void_p, LOGCB, C.c_void_p]
lib.fmi3FreeInstance.argtypes = [C.c_void_p]
for name in ["fmi3EnterInitializationMode"]:
    getattr(lib, name).argtypes = [C.c_void_p, C.c_bool, C.c_double, C.c_double, C.c_bool, C.c_double]
for name in ["fmi3ExitInitializationMode", "fmi3Terminate", "fmi3Reset"]:
    getattr(lib, name).argtypes = [C.c_void_p]
lib.fmi3DoStep.argtypes = [C.c_void_p, C.c_double, C.c_double, C.c_bool,
                           C.POINTER(C.c_bool), C.POINTER(C.c_bool), C.POINTER(C.c_bool), C.POINTER(C.c_double)]
for t, ct in [("Float64", C.c_double), ("Int32", C.c_int32), ("Boolean", C.c_bool), ("String", C.c_char_p)]:
    for op in ("Get", "Set"):
        getattr(lib, f"fmi3{op}{t}").argtypes = [C.c_void_p, C.POINTER(C.c_uint32), C.c_size_t, C.POINTER(ct), C.c_size_t]
lib.fmi3GetFMUState.argtypes = [C.c_void_p, C.POINTER(C.c_void_p)]
lib.fmi3SetFMUState.argtypes = [C.c_void_p, C.c_void_p]
lib.fmi3FreeFMUState.argtypes = [C.c_void_p, C.POINTER(C.c_void_p)]

def vrs(*v):
    return (C.c_uint32 * len(v))(*v)

def instantiate(logcb=logger, resources=None):
    res = str(fmu_dir / "resources") if resources is None else resources
    return inst_fn(b"inst", b"", res.encode(), False, True, False, False, None, 0, None, logcb, None)

def step(c, t, dt):
    ehn, term, early, last = C.c_bool(True), C.c_bool(True), C.c_bool(True), C.c_double(-1)
    st = lib.fmi3DoStep(c, t, dt, True, C.byref(ehn), C.byref(term), C.byref(early), C.byref(last))
    return st, ehn.value, term.value, early.value, last.value

# value references for tests/slaves/pythonslave.py
VR_INTPARAM, VR_REALIN, VR_BOOLPARAM, VR_STRPARAM, VR_REALOUT = 1, 2, 3, 4, 6

if scenario == "basic":
    c = instantiate()
    assert c
    assert lib.fmi3EnterInitializationMode(c, False, 0, 0, False, 0) == 0
    assert lib.fmi3ExitInitializationMode(c) == 0
    st, ehn, term, early, last = step(c, 0.0, 0.5)
    assert st == 0 and (ehn, term, early) == (False, False, False), (st, ehn, term, early)
    assert abs(last - 0.5) < 1e-12, last
    out = (C.c_double * 1)()
    assert lib.fmi3GetFloat64(c, vrs(VR_REALOUT), 1, out, 1) == 0
    assert out[0] == 0.5, out[0]
    iv = (C.c_int32 * 1)(7)
    assert lib.fmi3SetInt32(c, vrs(VR_INTPARAM), 1, iv, 1) == 0
    iv2 = (C.c_int32 * 1)()
    assert lib.fmi3GetInt32(c, vrs(VR_INTPARAM), 1, iv2, 1) == 0 and iv2[0] == 7
    sv = (C.c_char_p * 1)(b"cat")
    assert lib.fmi3SetString(c, vrs(VR_STRPARAM), 1, sv, 1) == 0
    sv2 = (C.c_char_p * 1)()
    assert lib.fmi3GetString(c, vrs(VR_STRPARAM), 1, sv2, 1) == 0 and sv2[0] == b"cat"
    bv = (C.c_bool * 1)(True)
    assert lib.fmi3SetBoolean(c, vrs(VR_BOOLPARAM), 1, bv, 1) == 0
    bv2 = (C.c_bool * 1)()
    assert lib.fmi3GetBoolean(c, vrs(VR_BOOLPARAM), 1, bv2, 1) == 0 and bv2[0]
    # FMU state round-trip, including overwriting an existing state
    state = C.c_void_p()
    assert lib.fmi3GetFMUState(c, C.byref(state)) == 0 and state.value
    step(c, 0.5, 0.5)
    assert lib.fmi3GetFMUState(c, C.byref(state)) == 0   # overwrite (old state must be released)
    assert lib.fmi3SetFMUState(c, state) == 0
    assert lib.fmi3FreeFMUState(c, C.byref(state)) == 0
    assert lib.fmi3Reset(c) == 0
    assert lib.fmi3Terminate(c) == 0
    lib.fmi3FreeInstance(c)
    print("OK basic")

elif scenario == "bad_vr_type":
    # Asking Float64 for an Int32 variable raises TypeError in Python -> error status, no crash
    c = instantiate()
    out = (C.c_double * 1)()
    st = lib.fmi3GetFloat64(c, vrs(VR_INTPARAM), 1, out, 1)
    assert st in (3, 4), st
    assert any("TypeError" in m for _, _, m in logs), logs
    lib.fmi3FreeInstance(c)   # previously: double Py_DECREF after an exception
    print("OK bad_vr_type", "traceback logged:", any("Traceback" in m for _, _, m in logs))

elif scenario == "too_few_values":
    # nValues larger than what Python returns -> was an out-of-bounds read
    c = instantiate()
    out = (C.c_double * 5)()
    st = lib.fmi3GetFloat64(c, vrs(VR_REALOUT), 1, out, 5)
    assert st != 0, st
    lib.fmi3FreeInstance(c)
    print("OK too_few_values", logs[-1][2][:80])

elif scenario == "exception_in_step":
    c = instantiate()
    lib.fmi3EnterInitializationMode(c, False, 0, 0, False, 0)
    lib.fmi3ExitInitializationMode(c)
    st = step(c, 0.0, 0.1)[0]
    assert st == 4, st  # fatal
    assert any("RuntimeError" in m for _, _, m in logs), logs
    lib.fmi3FreeInstance(c)
    print("OK exception_in_step")

elif scenario == "null_logger":
    c = inst_fn(b"inst", b"", str(fmu_dir / "resources").encode(), False, True, False, False,
                None, 0, None, C.cast(None, LOGCB), None)
    assert c
    out = (C.c_double * 5)()
    lib.fmi3GetFloat64(c, vrs(VR_REALOUT), 1, out, 5)  # error path logs -> must not call NULL
    lib.fmi3FreeInstance(c)
    print("OK null_logger")

elif scenario == "bad_resources":
    c = instantiate(resources="/does/not/exist")
    assert not c
    print("OK bad_resources", logs[-1][2][:60] if logs else "")

elif scenario == "uri_resources":
    c = instantiate(resources="file://" + str(fmu_dir / "resources").replace(" ", "%20") + "/")
    assert c
    lib.fmi3FreeInstance(c)
    print("OK uri_resources")

else:
    raise SystemExit(f"unknown scenario {scenario}")
