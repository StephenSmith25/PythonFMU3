"""Tests for examples/pipe_cht (only available in a source checkout)."""
import math
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path
from xml.etree.ElementTree import fromstring

import pytest

np = pytest.importorskip("numpy")

EXAMPLE = Path(__file__).parent.parent.parent / "examples" / "pipe_cht"
if not EXAMPLE.exists():
    pytest.skip("examples are only available in a source checkout", allow_module_level=True)

sys.path.insert(0, str(EXAMPLE))
import pipe1d  # noqa: E402
from pipe1d import N_SEGMENTS, Pipe1D  # noqa: E402


def make_pipe(n=N_SEGMENTS, **inputs):
    pipe = Pipe1D(instance_name="test")
    pipe.N = n
    pipe.enter_initialization_mode()
    pipe.exit_initialization_mode()
    for name, value in inputs.items():
        setattr(pipe, name, value)
    return pipe


def run_to_steady_state(pipe, steps=50, dt=1e4):
    t = 0.0
    for _ in range(steps):
        pipe.do_step(t, dt)
        t += dt
    return pipe


@pytest.mark.parametrize("m_dot", [0.005, 0.1])   # laminar and turbulent
def test_constant_wall_temperature_matches_analytic(m_dot):
    T_in, T_w = 293.15, 353.15
    pipe = run_to_steady_state(make_pipe(m_dot=m_dot, T_in=T_in, T_wall=np.full(N_SEGMENTS, T_w)))

    # Exact steady solution of the continuous problem: T_w - T = (T_w - T_in) exp(-h P x / (m_dot cp))
    ntu_per_length = pipe.h[0] * math.pi * pipe.diameter / (m_dot * pipe.cp)
    expected = T_w - (T_w - T_in) * np.exp(-ntu_per_length * (pipe.x + pipe.length / (2 * pipe.N)))
    # first-order upwind: compare the outlet (end of the last segment) within 2% of the temperature rise
    assert abs(pipe.T_out - expected[-1]) < 0.02 * (T_w - T_in)
    assert np.all(np.diff(pipe.T_fluid) > 0)


def test_resolution_converges_to_analytic():
    """First-order upwind: the outlet error shrinks as N grows."""
    T_in, T_w, m_dot = 293.15, 353.15, 0.005
    errors = []
    for n in (10, 40, 160):
        pipe = run_to_steady_state(make_pipe(n=n, m_dot=m_dot, T_in=T_in, T_wall=np.full(n, T_w)))
        ntu = pipe.h[0] * math.pi * pipe.diameter * pipe.length / (m_dot * pipe.cp)
        errors.append(abs(pipe.T_out - (T_w - (T_w - T_in) * math.exp(-ntu))))
    assert errors[0] > errors[1] > errors[2]
    assert errors[2] < 0.25 * errors[0]


def test_setting_N_resizes_arrays_through_the_fmi_api():
    pipe = Pipe1D(instance_name="test")
    n_vr = next(v.value_reference for v in pipe.vars.values() if v.name == "N")
    wall_vr = next(v.value_reference for v in pipe.vars.values() if v.name == "T_wall")
    fluid_vr = next(v.value_reference for v in pipe.vars.values() if v.name == "T_fluid")
    pipe.set_uint64([n_vr], [35])
    pipe.set_float64([wall_vr], list(np.linspace(300.0, 340.0, 35)))
    pipe.enter_initialization_mode()
    pipe.exit_initialization_mode()
    pipe.do_step(0.0, 1.0)
    assert len(pipe.get_float64([fluid_vr])) == 35
    assert pipe.T_wall.shape == (35,)
    with pytest.raises(ValueError):
        pipe.N = 0


def test_energy_is_conserved_at_steady_state():
    T_wall = np.linspace(300.0, 380.0, N_SEGMENTS)
    pipe = run_to_steady_state(make_pipe(m_dot=0.03, T_in=290.0, T_wall=T_wall))
    enthalpy_rise = pipe.m_dot * pipe.cp * (pipe.T_out - pipe.T_in)
    assert pipe.Q_total == pytest.approx(enthalpy_rise, rel=1e-9)


def test_reverse_flow_mirrors_forward_flow():
    T_wall = np.linspace(300.0, 380.0, N_SEGMENTS)
    forward = run_to_steady_state(make_pipe(m_dot=0.03, T_in=290.0, T_wall=T_wall))
    reverse = run_to_steady_state(make_pipe(m_dot=-0.03, T_in=290.0, T_wall=T_wall[::-1].copy()))
    np.testing.assert_allclose(reverse.T_fluid[::-1], forward.T_fluid, rtol=1e-12)
    assert reverse.T_out == pytest.approx(forward.T_out)


@pytest.mark.parametrize("re, nu", [(1000, 3.66), (9749, 64.6)])
def test_nusselt_correlation(re, nu):
    assert pipe1d.nusselt(re, 4.33) == pytest.approx(nu, rel=0.01)


def test_cht_demo_balances_heater_power():
    demo = subprocess.run(
        [sys.executable, str(EXAMPLE / "cht_demo.py"), "--end", "1800"],
        capture_output=True, text=True, timeout=300,
    )
    assert demo.returncode == 0, demo.stderr
    assert "(100.0% at t = 1800 s)" in demo.stdout or "(99.9% at t = 1800 s)" in demo.stdout, demo.stdout


def test_build_fmu(tmp_path):
    from pythonfmu3 import FmuBuilder

    fmu = FmuBuilder.build_FMU(EXAMPLE / "pipe1d.py", dest=tmp_path)
    with zipfile.ZipFile(fmu) as z:
        md = fromstring(z.read("modelDescription.xml"))
    variables = {v.get("name"): v for v in md.find("ModelVariables")}
    n = variables["N"]
    assert n.tag == "UInt64" and n.get("causality") == "structuralParameter" and n.get("start") == str(N_SEGMENTS)
    for name in ("T_wall", "T_fluid", "h", "x"):
        dims = variables[name].findall("Dimension")
        assert [d.get("valueReference") for d in dims] == [n.get("valueReference")]
    assert variables["T_wall"].get("causality") == "input"
    assert variables["h"].get("causality") == "output"


def test_fmu_matches_python_model(tmp_path):
    """Run the built FMU through the FMI C API (ctypes) and compare with the Python class."""
    from pythonfmu3 import FmuBuilder
    from pythonfmu3.builder import FmuBuilder as _B

    if not _B.has_binary():
        pytest.skip("needs the compiled wrapper")
    fmu = FmuBuilder.build_FMU(EXAMPLE / "pipe1d.py", dest=tmp_path)
    target = tmp_path / "pipe"
    with zipfile.ZipFile(fmu) as z:
        z.extractall(target)
        md = fromstring(z.read("modelDescription.xml"))
    vr = {v.get("name"): int(v.get("valueReference")) for v in md.find("ModelVariables")}

    n = 35   # not the default, set through Configuration Mode
    T_wall = np.linspace(300.0, 380.0, n)
    script = textwrap.dedent(f"""
        import ctypes as C, json, sys
        from pathlib import Path
        root = Path({str(target)!r})
        lib = C.CDLL(str(next(p for p in (root / "binaries").rglob("*.*")
                              if p.suffix in (".so", ".dylib", ".dll") and "backend" not in p.name)))
        lib.fmi3InstantiateCoSimulation.restype = C.c_void_p
        lib.fmi3InstantiateCoSimulation.argtypes = [C.c_char_p, C.c_char_p, C.c_char_p, C.c_bool, C.c_bool, C.c_bool,
            C.c_bool, C.c_void_p, C.c_size_t, C.c_void_p, C.c_void_p, C.c_void_p]
        for f in ("fmi3EnterInitializationMode",):
            getattr(lib, f).argtypes = [C.c_void_p, C.c_bool, C.c_double, C.c_double, C.c_bool, C.c_double]
        for f in ("fmi3ExitInitializationMode", "fmi3FreeInstance", "fmi3EnterConfigurationMode", "fmi3ExitConfigurationMode"):
            getattr(lib, f).argtypes = [C.c_void_p]
        lib.fmi3SetUInt64.argtypes = [C.c_void_p, C.POINTER(C.c_uint32), C.c_size_t, C.POINTER(C.c_uint64), C.c_size_t]
        lib.fmi3DoStep.argtypes = [C.c_void_p, C.c_double, C.c_double, C.c_bool, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p]
        for f in ("fmi3SetFloat64", "fmi3GetFloat64"):
            getattr(lib, f).argtypes = [C.c_void_p, C.POINTER(C.c_uint32), C.c_size_t, C.POINTER(C.c_double), C.c_size_t]
        def vrs(v): return (C.c_uint32 * 1)(v)
        c = lib.fmi3InstantiateCoSimulation(b"pipe", b"", str(root / "resources").encode(), False, False, False, False,
                                            None, 0, None, None, None)
        assert c
        assert lib.fmi3EnterConfigurationMode(c) == 0
        assert lib.fmi3SetUInt64(c, vrs({vr}["N"]), 1, (C.c_uint64 * 1)({n}), 1) == 0
        assert lib.fmi3ExitConfigurationMode(c) == 0
        assert lib.fmi3EnterInitializationMode(c, False, 0, 0, False, 0) == 0
        assert lib.fmi3ExitInitializationMode(c) == 0
        def set_(name, values):
            arr = (C.c_double * len(values))(*values)
            assert lib.fmi3SetFloat64(c, vrs({vr}[name]), 1, arr, len(values)) == 0
        def get(name, n):
            arr = (C.c_double * n)()
            assert lib.fmi3GetFloat64(c, vrs({vr}[name]), 1, arr, n) == 0
            return list(arr)
        set_("m_dot", [0.03]); set_("T_in", [290.0]); set_("T_wall", {T_wall.tolist()})
        flags = (C.c_bool * 3)(); last = C.c_double()
        t = 0.0
        for _ in range(5):
            assert lib.fmi3DoStep(c, t, 10.0, True, C.byref(flags, 0), C.byref(flags, 1), C.byref(flags, 2), C.byref(last)) == 0
            t += 10.0
        print(json.dumps({{"T_fluid": get("T_fluid", {n}), "h": get("h", {n}), "T_out": get("T_out", 1)}}))
        lib.fmi3FreeInstance(c)
    """)
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    import json
    result = json.loads(proc.stdout.strip().splitlines()[-1])

    reference = make_pipe(n=n, m_dot=0.03, T_in=290.0, T_wall=T_wall)
    t = 0.0
    for _ in range(5):
        reference.do_step(t, 10.0)
        t += 10.0
    assert len(result["T_fluid"]) == n
    np.testing.assert_allclose(result["T_fluid"], reference.T_fluid, rtol=1e-12)
    np.testing.assert_allclose(result["h"], reference.h, rtol=1e-12)
    assert result["T_out"][0] == pytest.approx(reference.T_out)
