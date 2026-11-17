"""PythonFMU3 in Jupyter notebooks.

    %load_ext pythonfmu3

    %%fmu
    class Tank(Fmi3Slave):
        ...

The ``%%fmu`` cell magic saves the cell as a model file, checks it and shows the FMU
block, its variables and any problems. The cell's class name is then bound to a
:class:`Model`, so you can carry on with ``Tank.simulate(...)`` and ``Tank.build()``.

Outside the magic, use ``Model("tank.py")`` for a model file and ``FMU("Tank.fmu")`` for
any FMU. Model code runs in a separate Python process each time, as in PythonFMU3 Studio,
so re-running a cell always uses the current code.

Simulation results are pandas DataFrames (``pip install "pythonfmu3[notebook]"``).
"""
import ast
import html
import re
import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional

MARKER = "# Written by the %%fmu cell magic: edit the notebook cell, not this file."
_STYLE_BOX = "font-family:system-ui,-apple-system,'Segoe UI',sans-serif;font-size:13px;line-height:1.4"
_LINE = "rgba(127,127,127,.35)"
_ACCENT = "#2F5D8A"
_GOLD = "#E8B11C"


def _worker(request: Dict[str, Any], cwd: Path) -> Dict[str, Any]:
    from .studio.server import run_worker
    return run_worker(request, cwd)


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _raise(response: Dict[str, Any], what: str):
    detail = response.get("traceback") or response.get("error") or "unknown error"
    raise RuntimeError(f"{what} failed:\n{detail}")


def _frame(result: Dict[str, Any]):
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError('Simulation results are pandas DataFrames: pip install "pythonfmu3[notebook]"') from exc
    frame = pd.DataFrame(result["series"], index=pd.Index(result["time"], name="time"))
    frame.attrs.update(simulator=result.get("simulator"), interface=result.get("interface"),
                       events=result.get("events", []))
    return frame


def _table(headers: List[str], rows: List[List[str]], max_rows: int = 200) -> str:
    cell = f"padding:4px 10px;border-bottom:1px solid {_LINE};text-align:left;vertical-align:top"
    head = "".join(f'<th style="{cell};font-weight:600">{_e(h)}</th>' for h in headers)
    body = "".join("<tr>" + "".join(f'<td style="{cell}">{c}</td>' for c in row) + "</tr>" for row in rows[:max_rows])
    more = f'<p style="opacity:.7">… and {len(rows) - max_rows} more</p>' if len(rows) > max_rows else ""
    return (f'<div style="overflow-x:auto"><table style="border-collapse:collapse;margin:6px 0">'
            f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>{more}")


def _block(name: str, interfaces: List[str], inputs: List[str], outputs: List[str], params: List[str]) -> str:
    def port(label, side):
        dot = f'<span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:{_GOLD}"></span>'
        text = f"<span>{_e(label)}</span>"
        return f'<div style="display:flex;gap:6px;align-items:center;justify-content:{side}">' + \
               (text + dot if side == "flex-end" else dot + text) + "</div>"
    chips = "".join(f'<span style="padding:2px 8px;border-radius:999px;background:rgba(232,177,28,.18);'
                    f'margin:2px;display:inline-block">{_e(p)}</span>' for p in params[:12])
    if len(params) > 12:
        chips += f'<span style="opacity:.7"> +{len(params) - 12} more</span>'
    kinds = " · ".join({"cs": "Co-Simulation", "me": "Model Exchange"}.get(i, i) for i in interfaces)
    return f"""
<div style="display:flex;flex-direction:column;align-items:center;gap:8px;margin:8px 0 12px">
  <div style="text-align:center;max-width:520px">{chips}</div>
  <div style="display:flex;align-items:center;gap:12px">
    <div style="display:flex;flex-direction:column;gap:6px;min-width:120px">{''.join(port(i, 'flex-end') for i in inputs[:16])}</div>
    <div style="background:{_ACCENT};color:#fff;border-radius:14px;padding:18px 24px;min-width:140px;text-align:center">
      <div style="font-weight:700;font-size:15px">{_e(name)}</div>
      <div style="opacity:.8;font-size:12px">{_e(kinds)}</div>
    </div>
    <div style="display:flex;flex-direction:column;gap:6px;min-width:120px">{''.join(port(o, 'flex-start') for o in outputs[:16])}</div>
  </div>
</div>"""


class Model:
    """A PythonFMU3 model file: check it, simulate it and build it from a notebook."""

    def __init__(self, path):
        self.path = Path(path).resolve()
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        self.analysis: Optional[Dict[str, Any]] = None
        self.error: Optional[Dict[str, Any]] = None

    # --- checks ------------------------------------------------------------------------

    def check(self) -> "Model":
        """Load the model in a fresh process and run PythonFMU3 Studio's checks."""
        r = _worker({"command": "analyze", "path": str(self.path)}, self.path.parent)
        self.analysis, self.error = (r["result"], None) if r.get("ok") else (None, r)
        self._checked_mtime = self.path.stat().st_mtime_ns
        return self

    def _ensure_checked(self):
        """Check the model if it hasn't been checked, or if the file changed since."""
        if getattr(self, "_checked_mtime", None) != self.path.stat().st_mtime_ns:
            self.check()

    @property
    def ok(self) -> bool:
        """True when the model loads and the checks found no errors."""
        self._ensure_checked()
        return self.analysis is not None and not any(c["level"] == "error" for c in self.analysis["checks"])

    @property
    def problems(self) -> List[str]:
        """Errors and warnings from the checks, as text."""
        self._ensure_checked()
        if self.error:
            return [f"error: {self.error.get('error')}"]
        return [f"{c['level']}: {c['title']}: {c['detail']}" for c in self.analysis["checks"] if c["level"] != "ok"]

    @property
    def variables(self) -> List[Dict[str, Any]]:
        """The registered variables (name, type, causality, variability, unit, start, ...)."""
        self._ensure_checked()
        return list(self.analysis["variables"]) if self.analysis else []

    # --- simulation and build ----------------------------------------------------------

    def simulate(self, stop_time: float = 10.0, step_size: Optional[float] = None,
                 start_values: Optional[Dict[str, Any]] = None, interface: Optional[str] = None,
                 simulator: str = "python", outputs: Optional[List[str]] = None):
        """Simulate the model and return a pandas DataFrame indexed by time.

        ``simulator="python"`` runs the class directly (quick); ``"fmpy"`` or ``"fmusim"``
        build the FMU and run it in that importer. ``interface`` is ``"cs"`` or ``"me"`` for
        models with both. Events are in ``result.attrs["events"]``.
        """
        if stop_time <= 0:
            raise ValueError("stop_time must be positive")
        step = step_size if step_size and step_size > 0 else stop_time / 500
        known = {v["name"] for v in self.variables}
        unknown = sorted(set(start_values or {}) - known)
        if self.analysis and unknown:
            raise ValueError(f"Unknown variable(s) {', '.join(unknown)}; the model has {', '.join(sorted(known))}")
        request = {"command": "simulate", "path": str(self.path), "simulator": simulator, "interface": interface,
                   "stopTime": stop_time, "stepSize": step, "startValues": start_values or {}}
        if outputs:
            request["outputs"] = list(outputs)
        r = _worker(request, self.path.parent)
        if not r.get("ok"):
            _raise(r, "Simulation")
        if r.get("stdout"):
            print(r["stdout"], end="")
        return _frame(r["result"])

    def build(self, dest=None) -> "FMU":
        """Build the FMU (into ``dest``, default the model's folder) and return it."""
        request = {"command": "build", "path": str(self.path)}
        request["dest"] = str(Path(dest).resolve()) if dest else str(self.path.parent)
        r = _worker(request, self.path.parent)
        if not r.get("ok"):
            _raise(r, "Building the FMU")
        return FMU(r["result"]["fmu"])

    # --- display -----------------------------------------------------------------------

    def __repr__(self):
        self._ensure_checked()
        if self.error:
            return f"<Model {self.path.name}: doesn't load: {self.error.get('error')}>"
        a = self.analysis
        state = "no problems" if not self.problems else f"{len(self.problems)} problem(s)"
        return f"<Model {a['className']} ({self.path.name}): {len(a['variables'])} variables, {state}>"

    def _repr_html_(self):
        self._ensure_checked()
        head = f'<div style="{_STYLE_BOX}">'
        if self.error:
            tb = self.error.get("traceback") or self.error.get("error")
            return (head + f'<div style="color:#c0392b;font-weight:600">{_e(self.path.name)} doesn\'t load</div>'
                    f'<pre style="white-space:pre-wrap;font-size:12px">{_e(tb)}</pre></div>')
        a = self.analysis
        vs = a["variables"]
        by = lambda *cs: [v["name"] + (f" [{v['unit']}]" if v["unit"] else "") for v in vs if v["causality"] in cs]
        parts = [head, _block(a["className"], a["interfaces"], by("input"), by("output"),
                              [f"{v['name']} = {v['start'] if v['start'] is not None else v['value']}"
                               for v in vs if v["causality"] in ("parameter", "structuralParameter")])]
        issues = [c for c in a["checks"] if c["level"] != "ok"]
        if issues:
            colour = {"error": "#c0392b", "warning": "#b7791f"}
            parts.append("".join(f'<div style="color:{colour.get(c["level"], "inherit")};margin:2px 0">'
                                 f'<b>{_e(c["level"])}:</b> {_e(c["title"])}: {_e(c["detail"])}</div>' for c in issues))
        else:
            parts.append('<div style="color:#2f855a;margin:2px 0">✓ No problems found</div>')
        rows = [[_e(v["vr"]), f"<code>{_e(v['name'])}</code>", _e(v["type"]), _e(v["causality"]),
                 _e(v["variability"]), _e(v["unit"]), _e(v["start"]), _e(v["description"])] for v in vs]
        parts.append(f'<details><summary style="cursor:pointer">Variables ({len(vs)})</summary>'
                     + _table(["vr", "name", "type", "causality", "variability", "unit", "start", "description"], rows)
                     + "</details>")
        parts.append(f'<div style="opacity:.65;font-size:12px">{_e(self.path)}</div></div>')
        return "".join(parts)


class FMU:
    """Any FMU file (FMI 2.0 or 3.0, from any tool): inspect it, validate it, simulate it."""

    def __init__(self, path):
        self.path = Path(path).resolve()
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        from .studio.worker import inspect_fmu         # only reads the archive, runs nothing
        self.info: Dict[str, Any] = inspect_fmu({"path": str(self.path)})

    @property
    def variables(self) -> List[Dict[str, Any]]:
        return list(self.info["variables"])

    def simulate(self, stop_time: float = 10.0, step_size: Optional[float] = None,
                 start_values: Optional[Dict[str, Any]] = None, interface: Optional[str] = None,
                 simulator: Optional[str] = None):
        """Simulate with FMPy or fmusim (``simulator``; default: whichever is installed) and
        return a pandas DataFrame indexed by time."""
        if stop_time <= 0:
            raise ValueError("stop_time must be positive")
        step = step_size if step_size and step_size > 0 else stop_time / 500
        r = _worker({"command": "simulate_fmu", "fmu": str(self.path), "simulator": simulator, "interface": interface,
                     "stopTime": stop_time, "stepSize": step, "startValues": start_values or {}}, self.path.parent)
        if not r.get("ok"):
            _raise(r, "Simulation")
        return _frame(r["result"])

    def validate(self) -> Dict[str, Any]:
        """Validate with fmusim if installed, otherwise basic archive checks."""
        r = _worker({"command": "validate", "fmu": str(self.path)}, self.path.parent)
        if not r.get("ok"):
            _raise(r, "Validation")
        return r["result"]

    def __repr__(self):
        i = self.info
        return (f"<FMU {i['modelName']} ({self.path.name}): FMI {i['fmiVersion']}, {', '.join(i['interfaces'])}, "
                f"{len(i['variables'])} variables, platforms: {', '.join(i['platforms']) or 'none'}>")

    def _repr_html_(self):
        i = self.info
        vs = i["variables"]
        names = lambda c: [v["name"] + (f" [{v['unit']}]" if v.get("unit") else "") for v in vs if v["causality"] == c]
        kinds = [{"CoSimulation": "cs", "ModelExchange": "me"}.get(k, k) for k in i["interfaces"]]
        facts = [("File", f"{self.path.name} ({i['size'] / 1e6:.2f} MB)"), ("FMI version", i["fmiVersion"]),
                 ("Platforms", ", ".join(i["platforms"]) or "none (no binaries)"),
                 ("Generated by", i.get("generationTool")), ("Description", i.get("description"))]
        rows = [[f"<b>{_e(k)}</b>", _e(v)] for k, v in facts if v]
        params = [v["name"] + (f" = {v['start']}" if v.get("start") else "") for v in vs if v["causality"] == "parameter"]
        parts = [f'<div style="{_STYLE_BOX}">', _block(i["modelName"], kinds, names("input"), names("output"), params),
                 _table(["", ""], rows)]
        for p in i["problems"]:
            parts.append(f'<div style="color:#c0392b"><b>problem:</b> {_e(p)}</div>')
        vrows = [[_e(v["vr"]), f"<code>{_e(v['name'])}</code>", _e(v["type"]), _e(v["causality"]),
                  _e(v["variability"]), _e(v["unit"]), _e(v["start"])] for v in vs]
        parts.append(f'<details><summary style="cursor:pointer">Variables ({len(vs)})</summary>'
                     + _table(["vr", "name", "type", "causality", "variability", "unit", "start"], vrows)
                     + "</details></div>")
        return "".join(parts)


# --- the %%fmu cell magic -----------------------------------------------------------------

def _class_name(source: str) -> Optional[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        match = re.search(r"^class\s+(\w+)", source, re.MULTILINE)
        return match.group(1) if match else None
    names = [node.name for node in tree.body if isinstance(node, ast.ClassDef)
             and any("Fmi3Slave" in ast.unparse(base) for base in node.bases)]
    if not names:
        names = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    return names[-1] if names else None


def _snake(name: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()


def fmu_cell(line: str, cell: str, namespace: Optional[Dict[str, Any]] = None) -> Model:
    """Implementation of ``%%fmu [file.py] [--dir DIR] [--build] [--overwrite]``."""
    import argparse

    parser = argparse.ArgumentParser(prog="%%fmu", add_help=False)
    parser.add_argument("file", nargs="?")
    parser.add_argument("-d", "--dir", default=".")
    parser.add_argument("-b", "--build", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    try:
        args = parser.parse_args(shlex.split(line or ""))
    except SystemExit:
        raise ValueError("usage: %%fmu [file.py] [--dir DIR] [--build] [--overwrite]") from None

    class_name = _class_name(cell)
    file_name = args.file or (f"{_snake(class_name)}.py" if class_name else None)
    if not file_name:
        raise ValueError("The cell has no model class; give a file name: %%fmu my_model.py")
    if not file_name.endswith(".py"):
        file_name += ".py"
    path = (Path(args.dir) / file_name).resolve()

    # One header line, so line numbers in errors are the cell's line numbers plus one.
    if re.search(r"^\s*(from|import)\s+pythonfmu3\b", cell, re.MULTILINE):
        header = MARKER
    else:
        header = f"from pythonfmu3 import *  {MARKER}"
    source = f"{header}\n{cell.rstrip()}\n"
    if path.exists() and not args.overwrite:
        first = path.read_text(encoding="utf-8").split("\n", 1)[0]
        if MARKER not in first:
            raise FileExistsError(f"{path} exists and wasn't written by %%fmu; use --overwrite or another file name")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")

    model = Model(path).check()
    if namespace is not None and class_name:
        namespace[class_name] = model
    if args.build and model.ok:
        try:
            from IPython.display import display
        except ImportError:                        # pragma: no cover - only used in IPython
            display = print
        display(model)
        return model.build()
    return model


def load_ipython_extension(ipython):
    """Called by ``%load_ext pythonfmu3`` (or ``%load_ext pythonfmu3.notebook``)."""
    def fmu(line, cell):
        return fmu_cell(line, cell, ipython.user_ns)
    fmu.__doc__ = fmu_cell.__doc__
    ipython.register_magic_function(fmu, magic_kind="cell", magic_name="fmu")
