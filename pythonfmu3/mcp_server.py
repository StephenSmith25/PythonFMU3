"""PythonFMU3 as an MCP server: lets AI agents (Claude, GitHub Copilot in VS Code, Cursor, ...)
write, check, simulate and build FMUs.

    pythonfmu3 mcp [folder]

The server talks MCP over stdio. It reads and writes only inside the workspace folder
(default: the current folder). Model code runs in a separate process for each request, as
in PythonFMU3 Studio.

Needs the optional ``mcp`` package: ``pip install "pythonfmu3[mcp]"`` (Python 3.10+).
"""
import csv
import functools
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ._version import __version__

GUIDE = """\
PythonFMU3 packages a Python class as an FMI 3.0 FMU (Functional Mock-up Unit) that simulation
tools can import. Work in this order: write the model, run_checks until there are no errors,
simulate to check the behaviour is plausible, then build_fmu.

Writing a model by hand:

    from pythonfmu3 import Fmi3Slave, Fmi3Causality, Fmi3Variability, Float64, Int32, Boolean, Unit

    class Tank(Fmi3Slave):                       # Co-Simulation
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.author = "..."                  # metadata must be set in __init__
            self.description = "..."
            self.time = 0.0                      # 1. create every attribute first...
            self.q_in = 0.0
            self.area = 2.0
            self.level = 1.0
            self.register_units([Unit(name="m", m=1), Unit(name="m3/s", m=3, s=-1), Unit(name="m2", m=2)])
            # 2. ...then register it (the variable name is the attribute name)
            self.register_variable(Float64("time", causality=Fmi3Causality.independent,
                                           variability=Fmi3Variability.continuous))
            self.register_variable(Float64("q_in", causality=Fmi3Causality.input, start=0.0, unit="m3/s"))
            self.register_variable(Float64("area", causality=Fmi3Causality.parameter,
                                           variability=Fmi3Variability.tunable, start=2.0, unit="m2"))
            self.register_variable(Float64("level", causality=Fmi3Causality.output, unit="m"))

        def do_step(self, current_time, step_size):
            self.level += self.q_in / self.area * step_size
            self.time = current_time + step_size
            return True                          # False stops the simulation

Rules: register a Float64 "time" (independent, continuous) and keep it updated; create attributes
before register_variable (otherwise inputs and parameters can't be set); only Float64 can be
continuous (Int32, Boolean, ... use discrete, or fixed/tunable for parameters); parameters use
variability fixed or tunable; give inputs and parameters start values; don't start names with "_";
one model class per file. Units: Unit(name, <SI base exponents kg m s A K mol cd rad>, factor=,
offset=), e.g. degC is Unit(name="degC", K=1, offset=273.15).

Model Exchange: inherit Fmi3SlaveBase and ModelExchange (add CoSimulation to support both).
Register each state (continuous, initial=Fmi3Initial.exact, start=...) and its derivative
(local, continuous, derivative=<value reference of the state>; value references count 0, 1, 2...
in registration order). Implement get_continuous_state_derivatives() returning the derivatives
in state order; for events use has_event_indicator=True, get_event_indicators() and
update_discrete_states(). The bouncing_ball template shows this.

Start from a template when one is close (list_templates, copy_template) and adapt it with
edit_model; edit_model is also the cheap way to fix problems.
The machine that runs the FMU needs Python and the packages the model imports, so prefer the
standard library and NumPy.
"""


INSTRUCTIONS = """\
PythonFMU3 builds FMI 3.0 FMUs from Python classes. Workflow: start from a template when one
is close (list_templates, copy_template), otherwise call get_guide before writing a model by
hand. Change models with edit_model (small replacements) rather than rewriting them with
write_model. Every change returns the model's checks; fix errors, simulate to check the
behaviour is plausible, and build_fmu only when the user wants the FMU.
"""


def _import_server_class():
    """Return (server class, ToolError) for the installed MCP SDK."""
    try:
        from mcp.server.mcpserver import MCPServer          # mcp >= 2
        from mcp.server.mcpserver.exceptions import ToolError
        return MCPServer, ToolError
    except ImportError:
        pass
    try:
        from mcp.server.fastmcp import FastMCP              # mcp 1.x
        from mcp.server.fastmcp.exceptions import ToolError
        return FastMCP, ToolError
    except ImportError as exc:
        raise SystemExit('The MCP server needs the "mcp" package (Python 3.10 or later):\n'
                         '    pip install "pythonfmu3[mcp]"') from exc


class Workspace:
    """Resolves paths: everything is read and written inside ``root``."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def path(self, value: str, must_exist: bool = True) -> Path:
        if not value or "\x00" in value:
            raise ValueError("empty path")
        p = Path(value).expanduser()
        p = (p if p.is_absolute() else self.root / p).resolve()
        if p != self.root and self.root not in p.parents:
            raise PermissionError(f"{value} is outside the workspace")
        if must_exist and not p.exists():
            raise FileNotFoundError(value)
        return p

    def rel(self, p: Path) -> str:
        p = Path(p).resolve()
        try:
            return p.relative_to(self.root).as_posix()
        except ValueError:
            return str(p)


def _worker(request: Dict[str, Any], cwd: Path) -> Dict[str, Any]:
    from .studio.server import run_worker
    return run_worker(request, cwd)


def _failure(r: Dict[str, Any]) -> Dict[str, Any]:
    out = {"ok": False, "error": r.get("error")}
    if r.get("traceback"):
        out["traceback"] = r["traceback"][-3000:]
    if r.get("stdout"):
        out["stdout"] = r["stdout"][-1000:]
    return out


def _summarize_analysis(a: Dict[str, Any]) -> Dict[str, Any]:
    def var(v):
        parts = [str(v["vr"]), v["name"], v["type"], v["causality"], v["variability"] or ""]
        if v["start"] is not None:
            parts.append(f"start={json.dumps(v['start'])}")
        if v["unit"]:
            parts.append(f"unit={v['unit']}")
        return " ".join(p for p in parts if p)
    return {
        "ok": True, "className": a["className"], "interfaces": a["interfaces"],
        "variables": [var(v) for v in a["variables"]],
        "problems": [f"{c['level']}: {c['title']}: {c['detail']}" for c in a["checks"] if c["level"] != "ok"],
    }


def _summarize_simulation(res: Dict[str, Any]) -> Dict[str, Any]:
    t = res["time"]
    n = len(t)
    idx = sorted({round(i * (n - 1) / 10) for i in range(11)})
    variables = {}
    for name, ys in list(res["series"].items())[:30]:
        nums = [y for y in ys if isinstance(y, (int, float)) and y == y and abs(y) != float("inf")]
        if not nums:
            variables[name] = {"note": "not numeric or not finite", "final": ys[-1] if ys else None}
            continue
        variables[name] = {"initial": ys[0], "final": ys[-1], "min": min(nums), "max": max(nums),
                           "samples": [ys[i] for i in idx]}
        if len(nums) < len(ys):
            variables[name]["non_finite"] = len(ys) - len(nums)
    return {"ok": True, "simulator": res.get("simulator"), "interface": res.get("interface"), "points": n,
            "end_time": t[-1] if t else None, "sample_times": [t[i] for i in idx],
            "events": len(res.get("events", [])), "first_events": res.get("events", [])[:5],
            "variables": variables}


def create_server(workspace: Path):
    """Create the MCP server for ``workspace``. Returns the server object (call ``.run()``)."""
    from .studio.server import TEMPLATE_INFO, TEMPLATES

    ws = Workspace(workspace)
    server_class, ToolError = _import_server_class()
    server = server_class("pythonfmu3", instructions=INSTRUCTIONS)

    def tool():
        """Register a tool; any exception reaches the agent as a readable tool error."""
        def register(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                try:
                    return fn(*args, **kwargs)
                except ToolError:
                    raise
                except Exception as exc:
                    raise ToolError(f"{type(exc).__name__}: {exc}") from exc
            server.tool()(wrapper)
            return fn                     # tools call each other undecorated
        return register

    @tool()
    def get_guide() -> str:
        """How to write PythonFMU3 models by hand: the API, the rules the checks enforce, and
        Model Exchange. Read it before writing a model that isn't based on a template."""
        return GUIDE

    @tool()
    def list_files() -> Dict[str, Any]:
        """List the .py models, .fmu files and simulation results (.csv) in the workspace."""
        kinds = {".py": "model", ".fmu": "fmu", ".csv": "result"}
        files = []
        for p in sorted(ws.root.rglob("*")):
            if p.is_file() and p.suffix.lower() in kinds and not any(part.startswith(".") or part == "__pycache__"
                                                                     for part in p.relative_to(ws.root).parts):
                files.append(f"{ws.rel(p)} ({kinds[p.suffix.lower()]}, {p.stat().st_size} bytes)")
                if len(files) >= 500:
                    break
        return {"workspace": str(ws.root), "files": files}

    @tool()
    def read_file(path: str) -> Dict[str, Any]:
        """Read a model (.py) or another text file from the workspace."""
        p = ws.path(path)
        if p.stat().st_size > 2_000_000:
            raise ValueError("File is larger than 2 MB")
        return {"path": ws.rel(p), "content": p.read_text(encoding="utf-8", errors="replace")}

    @tool()
    def write_model(path: str, content: str) -> Dict[str, Any]:
        """Create or overwrite a .py model file in the workspace and return its checks
        (variables and problems). Read an existing file before overwriting it."""
        p = ws.path(path, must_exist=False)
        if p.suffix != ".py":
            raise ValueError("Model files must end in .py")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        result = run_checks(ws.rel(p))
        return {"saved": ws.rel(p), **result}

    @tool()
    def edit_model(path: str, old_text: str, new_text: str, replace_all: bool = False) -> Dict[str, Any]:
        """Change part of a .py model: replace old_text (copied exactly, including indentation,
        and unique in the file unless replace_all) with new_text, then return the checks.
        Cheaper than rewriting the whole file with write_model."""
        p = ws.path(path)
        if p.suffix != ".py":
            raise ValueError("Only .py models can be edited")
        if not old_text:
            raise ValueError("old_text is empty")
        content = p.read_text(encoding="utf-8")
        count = content.count(old_text)
        if count == 0:
            raise ValueError("old_text was not found; read_file to see the current content")
        if count > 1 and not replace_all:
            raise ValueError(f"old_text occurs {count} times; include more context or set replace_all")
        p.write_text(content.replace(old_text, new_text) if replace_all else content.replace(old_text, new_text, 1),
                     encoding="utf-8")
        return {"saved": ws.rel(p), "replacements": count if replace_all else 1, **run_checks(ws.rel(p))}

    @tool()
    def copy_template(name: str, path: Optional[str] = None) -> Dict[str, Any]:
        """Copy an example model (see list_templates) into the workspace as a starting point and
        return its content and checks. Then adapt it with edit_model."""
        if name not in TEMPLATE_INFO:
            raise ValueError(f"Unknown template {name!r}; choose from {', '.join(TEMPLATE_INFO)}")
        target = ws.path(path or f"{name}.py", must_exist=False)
        if target.suffix != ".py":
            raise ValueError("path must end in .py")
        if target.exists():
            stem, i = target.stem, 2
            while target.exists():
                target = target.with_name(f"{stem}_{i}.py")
                i += 1
        content = (TEMPLATES / f"{name}.py").read_text(encoding="utf-8")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"saved": ws.rel(target), "content": content, **run_checks(ws.rel(target))}

    @tool()
    def run_checks(path: str) -> Dict[str, Any]:
        """Load a model and return its interfaces, variables and any problems."""
        p = ws.path(path)
        r = _worker({"command": "analyze", "path": str(p)}, p.parent)
        return _summarize_analysis(r["result"]) if r.get("ok") else _failure(r)

    @tool()
    def simulate(path: str, stop_time: float = 10.0, step_size: Optional[float] = None,
                 simulator: str = "python", interface: Optional[str] = None,
                 start_values: Optional[Dict[str, Any]] = None,
                 variables: Optional[List[str]] = None) -> Dict[str, Any]:
        """Simulate a model and return a summary per variable (initial, final, min, max and 11
        samples) for its outputs, or for `variables` if given (any recorded names, e.g. locals
        or states). The full result, with every variable, is saved as CSV in results/.
        simulator: "python" (runs the class directly, quick), "fmusim" or "fmpy" (build the FMU
        and run it in that importer, if installed). interface: "cs" or "me", only for models
        with both."""
        p = ws.path(path)
        if stop_time <= 0:
            raise ValueError("stop_time must be positive")
        step = step_size if step_size and step_size > 0 else stop_time / 500
        if stop_time / step > 200_000:
            raise ValueError("Too many output points: increase step_size")
        r = _worker({"command": "simulate", "path": str(p), "simulator": simulator, "interface": interface,
                     "stopTime": stop_time, "stepSize": step, "startValues": start_values or {}}, p.parent)
        if not r.get("ok"):
            return _failure(r)
        res = r["result"]
        out_dir = ws.root / "results"
        out_dir.mkdir(exist_ok=True)
        csv_path = out_dir / f"{p.stem}.csv"
        names = list(res["series"])
        with csv_path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time", *names])
            for i, t in enumerate(res["time"]):
                w.writerow([t, *(res["series"][n][i] for n in names)])
        series = res["series"]
        if variables:
            keep = [n for n in series if n in variables or n.split("[")[0] in variables]
        else:
            causality = res.get("causality") or {}
            keep = [n for n in series if causality.get(n.split("[")[0]) == "output"] or list(series)
        hidden = len(series) - len(keep)
        summary = _summarize_simulation(dict(res, series={n: series[n] for n in keep}))
        if hidden:
            summary["not_shown"] = f"{hidden} more variables in the CSV; pass variables=[...] to see them"
        summary["csv"] = ws.rel(csv_path)
        if r.get("stdout"):
            summary["stdout"] = r["stdout"][-1000:]
        return summary

    @tool()
    def build_fmu(path: str) -> Dict[str, Any]:
        """Build a model into an .fmu in the build/ folder next to it."""
        p = ws.path(path)
        r = _worker({"command": "build", "path": str(p)}, p.parent)
        if not r.get("ok"):
            return _failure(r)
        res = r["result"]
        out = {"ok": True, "fmu": ws.rel(Path(res["fmu"])), "size_bytes": res["size"], "platforms": res["platforms"]}
        if not res["platforms"]:
            out["warning"] = ("The FMU has no binaries for any platform, so importers can't run it: "
                              "PythonFMU3's native library isn't built for this platform.")
        return out

    @tool()
    def inspect_fmu(path: str) -> Dict[str, Any]:
        """Describe any FMI 2.0 or 3.0 FMU: interfaces, platforms, variables and archive problems.
        The FMU is only read, never run."""
        p = ws.path(path)
        r = _worker({"command": "inspect", "path": str(p), "name": p.name}, ws.root)
        if not r.get("ok"):
            return _failure(r)
        res = r["result"]
        res["variables"] = [f"{v.get('name')} {v.get('type')} {v.get('causality')}" +
                            (f" unit={v['unit']}" if v.get("unit") else "") for v in res.get("variables", [])][:300]
        return {"ok": True, **res}

    @tool()
    def validate_fmu(path: str) -> Dict[str, Any]:
        """Validate an FMU with fmusim if it is installed, otherwise with basic archive checks."""
        p = ws.path(path)
        r = _worker({"command": "validate", "fmu": str(p)}, ws.root)
        return {"ok": True, **r["result"]} if r.get("ok") else _failure(r)

    @tool()
    def list_templates() -> Dict[str, Any]:
        """List the example models that come with PythonFMU3."""
        return {"templates": [f"{key}: {title} ({iface}) - {desc}"
                              for key, (title, iface, _cats, desc, _tags) in TEMPLATE_INFO.items()
                              if (TEMPLATES / f"{key}.py").exists()]}

    @tool()
    def read_template(name: str) -> Dict[str, Any]:
        """Read the source of an example model, e.g. "bouncing_ball" or "thermostat", for
        reference. To start a model from it, use copy_template instead."""
        if name not in TEMPLATE_INFO:
            raise ValueError(f"Unknown template {name!r}; choose from {', '.join(TEMPLATE_INFO)}")
        return {"name": name, "content": (TEMPLATES / f"{name}.py").read_text(encoding="utf-8")}

    return server


def main(folder: str = "."):
    workspace = Path(folder).expanduser().resolve()
    if not workspace.is_dir():
        raise SystemExit(f"No such folder: {workspace}")
    server = create_server(workspace)
    print(f"PythonFMU3 {__version__} MCP server, workspace {workspace}", file=sys.stderr)
    server.run()


def create_command_parser(parser):
    parser.add_argument("folder", nargs="?", default=".",
                        help="Workspace folder: models are read and written here (default: current folder)")
    parser.set_defaults(execute=main)
