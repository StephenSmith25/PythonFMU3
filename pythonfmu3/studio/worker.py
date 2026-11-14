"""Studio worker: analyses, simulates and builds a model in a separate process.

Each request runs in a fresh interpreter (``python -m pythonfmu3.studio.worker``) so that
user code is imported from scratch every time and cannot affect the server. The request
is read as JSON from stdin; the response is written as JSON to stdout. Anything the
model prints is captured and returned in the response's ``stdout`` field.
"""
import contextlib
import importlib.util
import io
import json
import math
import shutil
import subprocess
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.dom.minidom import parseString
from xml.etree.ElementTree import tostring

PARAMETER_CAUSALITIES = ("parameter", "structuralParameter")
METADATA = ("author", "description", "license", "version", "copyright")


# --- loading -----------------------------------------------------------------------------

def load_model_class(path: Path):
    """Import the script in ``path`` and return its FMU class."""
    from pythonfmu3.builder import _find_slave_class

    module_name = f"studio_model_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    return _find_slave_class(module, path)


def instantiate(cls, path: Path):
    sys.path.insert(0, str(path.parent))
    try:
        return cls(instance_name="studio", resources=str(path.parent))
    finally:
        sys.path.remove(str(path.parent))


def interfaces_of(instance) -> List[str]:
    from pythonfmu3 import CoSimulation, ModelExchange

    result = []
    if isinstance(instance, CoSimulation):
        result.append("cs")
    if isinstance(instance, ModelExchange):
        result.append("me")
    return result


def jsonable(value: Any):
    try:
        import numpy as np
        if isinstance(value, np.ndarray):
            return [jsonable(v) for v in value.ravel().tolist()]
        if isinstance(value, np.generic):
            return value.item()
    except ImportError:
        pass
    if hasattr(value, "value") and not isinstance(value, (int, float, str, bool)):
        return jsonable(value.value)          # ctypes values, enum members
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def variable_info(instance, var) -> Dict[str, Any]:
    dims = list(getattr(var, "dimensions", []) or [])
    size = None
    if dims:
        try:
            size = int(var.size(instance.vars))
        except Exception:
            size = None
    try:
        value = jsonable(var.getter())
    except Exception as exc:              # reported by the checks
        value = f"<error: {exc}>"
    return {
        "vr": var.value_reference,
        "name": var.name,
        "type": type(var).__name__,
        "causality": var.causality.name if var.causality else "local",
        "variability": var.variability.name if var.variability else None,
        "initial": var.initial.name if var.initial else None,
        "unit": getattr(var, "unit", None),
        "description": var.description,
        "start": jsonable(getattr(var, "start", None)),
        "value": value,
        "dims": [d.start or f"vr {d.value_reference}" for d in dims],
        "size": size,
        "settable": var.setter is not None,
        "derivative": getattr(var, "derivative", None),
    }


# --- checks ------------------------------------------------------------------------------

def run_checks(cls, instance, variables: List[Dict[str, Any]], xml_ok: Optional[str]) -> List[Dict[str, str]]:
    checks = []

    def add(level, title, detail, name=None):
        checks.append({"level": level, "title": title, "detail": detail, "variable": name})

    if xml_ok:
        add("error", "Model description", xml_ok)

    if not any(v["causality"] == "independent" for v in variables):
        add("error", "Independent variable",
            "FMI 3.0 expects time to be declared: register a Float64 with causality=Fmi3Causality.independent.")

    for v in variables:
        if v["type"] != "Float64" and v["variability"] in (None, "continuous"):
            add("warning", f"{v['name']}: variability",
                f"{v['type']} variables can't be continuous. Use variability=Fmi3Variability.discrete "
                "(or fixed/tunable for parameters).", v["name"])
        settable = v["causality"] in ("input",) + PARAMETER_CAUSALITIES and v["variability"] != "constant"
        if settable and not v["settable"]:
            add("error", f"{v['name']}: not settable",
                "No setter was created, so importers can't set it. Create the attribute before "
                "register_variable, or pass setter=.", v["name"])
        if v["name"].lstrip(".").startswith("_") or "._" in v["name"]:
            add("warning", f"{v['name']}: leading underscore",
                "PythonFMU3 strips leading underscores when it looks up the attribute "
                f"(it reads self.{v['name'].lstrip('_')}). Rename it or pass getter=/setter=.", v["name"])
        if isinstance(v["value"], str) and v["value"].startswith("<error"):
            add("error", f"{v['name']}: getter failed", v["value"], v["name"])

    for attr in METADATA:
        if attr in vars(cls) and isinstance(vars(cls)[attr], str) and getattr(instance, attr, None) is None:
            add("warning", f"Class attribute {attr!r} is ignored",
                f"Set self.{attr} = ... in __init__ instead; class-level values don't reach the model description.")

    if not interfaces_of(instance):
        add("error", "Interface", "The class must inherit Fmi3Slave (Co-Simulation) or a ModelExchange mixin.")

    if not any(c["level"] == "error" for c in checks):
        add("ok", "Model description", "Generated without errors.")
    return checks


# --- analyze -----------------------------------------------------------------------------

def analyze(req: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(req["path"]).resolve()
    cls = load_model_class(path)
    instance = instantiate(cls, path)

    xml_text, xml_error = "", None
    try:
        root = instance.to_xml()
        xml_text = parseString(tostring(root, "UTF-8")).toprettyxml(indent="  ")
        xml_text = "\n".join(line for line in xml_text.splitlines()[1:] if line.strip())
    except Exception as exc:
        xml_error = f"{type(exc).__name__}: {exc}"

    variables = [variable_info(instance, v) for v in instance.vars.values()]
    de = instance.default_experiment
    return {
        "className": cls.__name__,
        "modelName": instance.modelName,
        "description": instance.description,
        "author": instance.author,
        "interfaces": interfaces_of(instance),
        "variables": variables,
        "eventIndicators": len(getattr(instance, "event_indicators", [])),
        "defaultExperiment": {
            "startTime": getattr(de, "start_time", None), "stopTime": getattr(de, "stop_time", None),
            "stepSize": getattr(de, "step_size", None), "tolerance": getattr(de, "tolerance", None),
        } if de else None,
        "xml": xml_text,
        "checks": run_checks(cls, instance, variables, xml_error),
    }


# --- simulate ----------------------------------------------------------------------------

def _set_start_values(instance, values: Dict[str, Any]):
    by_name = {v.name: v for v in instance.vars.values()}
    for name, value in (values or {}).items():
        var = by_name.get(name)
        if var is None or var.setter is None:
            continue
        kind = type(var).__name__
        if kind in ("Int32", "Int64", "UInt64", "Enumeration"):
            value = int(float(value))
        elif kind == "Boolean":
            value = value in (True, 1, "1", "true", "True")
        elif kind == "Float64" and not isinstance(value, list):
            value = float(value)
        var.setter(value)


def _recorded(instance, names: Optional[List[str]]):
    keep = []
    for var in instance.vars.values():
        if names is not None:
            if var.name in names:
                keep.append(var)
        elif var.causality is not None and var.causality.name in ("output", "local") \
                and type(var).__name__ in ("Float64", "Int32", "Int64", "UInt64", "Boolean", "Enumeration"):
            keep.append(var)
    return keep


def _sample(series, recorded):
    for var in recorded:
        value = jsonable(var.getter())
        if isinstance(value, list):
            for i, item in enumerate(value[:16]):
                series.setdefault(f"{var.name}[{i + 1}]", []).append(_num(item))
        else:
            series.setdefault(var.name, []).append(_num(value))


def _num(value):
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def simulate_python(req: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(req["path"]).resolve()
    cls = load_model_class(path)
    instance = instantiate(cls, path)
    interface = req.get("interface") or interfaces_of(instance)[0]
    start, stop = float(req.get("startTime", 0.0)), float(req["stopTime"])
    step = float(req["stepSize"])
    _set_start_values(instance, req.get("startValues"))
    instance.enter_initialization_mode()
    instance.exit_initialization_mode()
    recorded = _recorded(instance, req.get("outputs"))
    times, series, events = [start], {}, []
    _sample(series, recorded)

    if interface == "cs":
        n = max(1, int(round((stop - start) / step)))
        t = start
        for i in range(n):
            result = instance.do_step(t, step)
            t = round(start + (i + 1) * step, 12)
            times.append(t)
            _sample(series, recorded)
            if result is False or getattr(result, "terminateSimulation", False):
                events.append({"t": t, "kind": "terminate"})
                break
            if getattr(result, "status", 0) not in (0,):
                events.append({"t": t, "kind": f"status {int(result.status)}"})
    else:
        times, series, events = _simulate_me(instance, recorded, start, stop, step)
    return {"interface": interface, "time": times, "series": series, "events": events, "simulator": "python"}


def _simulate_me(instance, recorded, start, stop, step):
    """Fixed-step RK4 with event location (bisection) on the event indicators."""
    n_states = instance.get_number_of_continuous_states()
    n_ind = instance.get_number_of_event_indicators()

    def set_state(t, x):
        instance.time = t
        if n_states:
            instance.set_continuous_states(list(x))

    def deriv(t, x):
        set_state(t, x)
        return list(instance.get_continuous_state_derivatives()) if n_states else []

    def indicators(t, x):
        set_state(t, x)
        return list(instance.get_event_indicators()) if n_ind else []

    def rk4(t, x, h):
        k1 = deriv(t, x)
        k2 = deriv(t + h / 2, [xi + h / 2 * ki for xi, ki in zip(x, k1)])
        k3 = deriv(t + h / 2, [xi + h / 2 * ki for xi, ki in zip(x, k2)])
        k4 = deriv(t + h, [xi + h * ki for xi, ki in zip(x, k3)])
        return [xi + h / 6 * (a + 2 * b + 2 * c + d) for xi, a, b, c, d in zip(x, k1, k2, k3, k4)]

    def record(t, x):
        set_state(t, x)
        if n_states:
            instance.get_continuous_state_derivatives()
        times.append(t)
        _sample(series, recorded)

    times, series, events = [], {}, []
    t = start
    x = list(instance.get_continuous_states()) if n_states else []
    record(t, x)
    z = indicators(t, x)
    h_sub = step / 10.0                    # internal steps per output interval
    n_out = max(1, int(round((stop - start) / step)))
    for k in range(1, n_out + 1):
        t_out = round(start + k * step, 12)
        while t < t_out - 1e-12:
            h = min(h_sub, t_out - t)
            x_new = rk4(t, x, h)
            z_new = indicators(t + h, x_new)
            crossed = [i for i in range(n_ind) if (z[i] > 0) != (z_new[i] > 0)]
            if crossed:
                lo, hi = 0.0, h                # locate the crossing by bisection
                for _ in range(50):
                    mid = (lo + hi) / 2
                    z_mid = indicators(t + mid, rk4(t, x, mid))
                    if any((z[i] > 0) != (z_mid[i] > 0) for i in crossed):
                        hi = mid
                    else:
                        lo = mid
                t, x = t + hi, rk4(t, x, hi)
                set_state(t, x)
                for _ in range(100):
                    result = instance.update_discrete_states()
                    if not getattr(result, "discreteStatesNeedUpdate", False):
                        break
                events.append({"t": t, "kind": "state event"})
                x = list(instance.get_continuous_states()) if n_states else []
                z = indicators(t, x)
                if getattr(result, "terminateSimulation", False):
                    record(t, x)
                    return times, series, events
            else:
                t, x, z = t + h, x_new, z_new
        record(t_out, x)
    return times, series, events


def find_fmusim() -> Optional[str]:
    import os
    candidate = os.environ.get("PYTHONFMU3_FMUSIM") or shutil.which("fmusim")
    return candidate if candidate and Path(candidate).exists() else None


def simulate_fmusim(req: Dict[str, Any]) -> Dict[str, Any]:
    fmusim = find_fmusim()
    if not fmusim:
        raise RuntimeError("fmusim was not found on PATH (or in PYTHONFMU3_FMUSIM)")
    path = Path(req["path"]).resolve()
    with tempfile.TemporaryDirectory(prefix="studio_") as tmp:
        fmu = _build(path, Path(tmp))["fmu"]
        out = Path(tmp) / "result.csv"
        cmd = [fmusim, "simulate", fmu, "--stop-time", str(req["stopTime"]),
               "--output-interval", str(req["stepSize"]), "--output-file", str(out)]
        if req.get("interface"):
            cmd += ["--interface-type", req["interface"]]
        for name, value in (req.get("startValues") or {}).items():
            cmd += ["--start-value", f"{name}={value}"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError(f"fmusim failed:\n{proc.stdout}\n{proc.stderr}".strip())
        times, series = _read_csv(out)
    return {"interface": req.get("interface"), "time": times, "series": series, "events": [],
            "simulator": "fmusim", "log": proc.stderr[-4000:]}


def simulate_fmpy(req: Dict[str, Any]) -> Dict[str, Any]:
    import fmpy

    path = Path(req["path"]).resolve()
    with tempfile.TemporaryDirectory(prefix="studio_") as tmp:
        fmu = _build(path, Path(tmp))["fmu"]
        result = fmpy.simulate_fmu(
            fmu, stop_time=float(req["stopTime"]), output_interval=float(req["stepSize"]),
            fmi_type={"cs": "CoSimulation", "me": "ModelExchange"}.get(req.get("interface"), None),
            start_values=req.get("startValues") or {},
        )
    times = [float(t) for t in result["time"]]
    series = {name: [float(v) for v in result[name]] for name in result.dtype.names if name != "time"}
    return {"interface": req.get("interface"), "time": times, "series": series, "events": [], "simulator": "fmpy"}


def _read_csv(path: Path):
    import csv
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    header = [h.strip().strip('"') for h in rows[0]]
    times, series = [], {h: [] for h in header[1:]}
    for row in rows[1:]:
        if not row:
            continue
        times.append(float(row[0]))
        for h, cell in zip(header[1:], row[1:]):
            series[h].append(_num(cell.split(" ")[0]) if cell else None)
    return times, series


def simulate(req: Dict[str, Any]) -> Dict[str, Any]:
    simulator = req.get("simulator", "python")
    if simulator == "fmusim":
        return simulate_fmusim(req)
    if simulator == "fmpy":
        return simulate_fmpy(req)
    return simulate_python(req)


# --- build / validate / inspect ----------------------------------------------------------

def _build(path: Path, dest: Path) -> Dict[str, Any]:
    from pythonfmu3 import FmuBuilder

    fmu = FmuBuilder.build_FMU(path, dest=dest)
    info = inspect_fmu({"path": str(fmu)})
    return {"fmu": str(fmu), "size": fmu.stat().st_size, "platforms": info["platforms"]}


def build(req: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(req["path"]).resolve()
    dest = Path(req.get("dest") or path.parent / "build").resolve()
    dest.mkdir(parents=True, exist_ok=True)
    return _build(path, dest)


def validate(req: Dict[str, Any]) -> Dict[str, Any]:
    fmu = Path(req["fmu"]).resolve()
    fmusim = find_fmusim()
    if fmusim:
        proc = subprocess.run([fmusim, "validate", str(fmu)], capture_output=True, text=True, timeout=120)
        return {"tool": "fmusim", "passed": proc.returncode == 0,
                "output": (proc.stdout + proc.stderr).strip()}
    info = inspect_fmu({"path": str(fmu)})
    return {"tool": "built-in", "passed": not info["problems"], "output": "\n".join(info["problems"]) or
            "ZIP archive and model description read without problems (install fmusim for a full check)."}


def inspect_fmu(req: Dict[str, Any]) -> Dict[str, Any]:
    from xml.etree.ElementTree import fromstring

    problems: List[str] = []
    with zipfile.ZipFile(req["path"]) as z:
        names = z.namelist()
        if "modelDescription.xml" not in names:
            raise ValueError("Not an FMU: modelDescription.xml is missing")
        root = fromstring(z.read("modelDescription.xml"))
    platforms = sorted({n.split("/")[1] for n in names if n.startswith("binaries/") and n.count("/") >= 2 and n.split("/")[1]})
    interfaces = [tag for tag in ("CoSimulation", "ModelExchange", "ScheduledExecution") if root.find(tag) is not None]
    for tag in interfaces:
        ident = root.find(tag).get("modelIdentifier")
        for plat in platforms:
            if not any(n.startswith(f"binaries/{plat}/{ident}.") for n in names):
                problems.append(f"{tag}: no binary for {ident} in binaries/{plat}/")
    variables = []
    mv = root.find("ModelVariables")
    for i, v in enumerate(list(mv) if mv is not None else []):
        dims = [d.get("start") or f"vr {d.get('valueReference')}" for d in v.findall("Dimension")]
        variables.append({
            "vr": v.get("valueReference", str(i)), "name": v.get("name"),
            "type": v.tag if v.tag != "ScalarVariable" else next((c.tag for c in v if c.tag != "Annotations"), "?"),
            "causality": v.get("causality", "local"), "variability": v.get("variability", ""),
            "start": v.get("start", ""), "unit": v.get("unit", ""), "description": v.get("description", ""),
            "dims": dims,
        })
    caps = {}
    for tag in interfaces:
        caps[tag] = {k: v for k, v in root.find(tag).attrib.items() if k != "modelIdentifier"}
    units = root.find("UnitDefinitions")
    de = root.find("DefaultExperiment")
    return {
        "fileName": Path(req.get("name") or req["path"]).name,
        "size": Path(req["path"]).stat().st_size,
        "fmiVersion": root.get("fmiVersion"),
        "modelName": root.get("modelName"),
        "description": root.get("description"),
        "author": root.get("author"),
        "generationTool": root.get("generationTool"),
        "generationDateAndTime": root.get("generationDateAndTime"),
        "token": root.get("instantiationToken") or root.get("guid"),
        "interfaces": interfaces,
        "capabilities": caps,
        "platforms": platforms,
        "sources": any(n.startswith("sources/") for n in names),
        "units": len(list(units)) if units is not None else 0,
        "defaultExperiment": dict(de.attrib) if de is not None else None,
        "variables": variables,
        "files": len(names),
        "problems": problems,
    }


COMMANDS = {"analyze": analyze, "simulate": simulate, "build": build, "validate": validate, "inspect": inspect_fmu}


def main():
    request = json.loads(sys.stdin.read() or "{}")
    real_stdout = sys.stdout
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):
            result = COMMANDS[request["command"]](request)
        response = {"ok": True, "result": result}
    except Exception as exc:
        response = {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc()}
    response["stdout"] = captured.getvalue()[-8000:]
    real_stdout.write(json.dumps(response, default=str))
    real_stdout.flush()


if __name__ == "__main__":
    main()
