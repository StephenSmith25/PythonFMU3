"""PythonFMU3 Studio: a local web app to edit, check, simulate, build and inspect FMUs.

Start it with ``pythonfmu3 studio [folder]``. It uses only the standard library: a
threaded HTTP server on 127.0.0.1 serving the static app and a small JSON API. Model
code runs in a separate worker process per request (see worker.py).

Security: the server only listens on the loopback interface, only answers requests
whose Host header is the loopback address, and requires a random token (generated per
run and passed to the browser in the URL) on every API call, so other web pages open in
the browser can't drive it.
"""
import argparse
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, quote, urlparse

from .._version import __version__

HERE = Path(__file__).parent
STATIC = HERE / "static"
TEMPLATES = HERE / "templates"
WORKER_TIMEOUT = 300
MAX_UPLOAD = 200 * 1024 * 1024
TEMPLATE_INFO = {
    "pid_controller": ("PID controller", "Co-Simulation", "control",
                       "Setpoint and measurement in, actuator command out, with tunable gains and output limits.",
                       ["inputs", "tunable parameters"]),
    "bouncing_ball": ("Bouncing ball", "Model Exchange", "me",
                      "Free fall with a state event at each impact and a restitution coefficient.",
                      ["events", "units"]),
    "van_der_pol": ("Van der Pol", "Model Exchange", "me",
                    "A nonlinear oscillator with two continuous states, for testing solvers.",
                    ["continuous states"]),
    "dahlquist": ("Dahlquist", "Model Exchange + Co-Simulation", "me cs",
                  "dx/dt = -k·x in both interfaces: the smallest model, with an exact solution.",
                  ["both interfaces"]),
    "thermostat": ("Thermostat", "Co-Simulation", "control",
                   "A heated room with on/off control and hysteresis: Boolean output and a discrete state.",
                   ["Boolean", "discrete"]),
    "surrogate": ("Polynomial surrogate", "Co-Simulation", "ml",
                  "A fitted NumPy polynomial exposed as an FMU: the pattern for ML surrogate models.",
                  ["numpy", "data-driven"]),
    "signal_generator": ("Signal generator", "Co-Simulation", "cs",
                         "Sine, square and ramp signals selected by an Int32 mode: a test-bench source.",
                         ["Int32 mode", "outputs"]),
}


class StudioState:
    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()
        self.token = secrets.token_urlsafe(24)
        self.uploads = Path(tempfile.mkdtemp(prefix="pythonfmu3_studio_"))
        self.last_build: Dict[str, str] = {}

    def resolve(self, relative: str, must_exist: bool = True) -> Path:
        """Resolve a workspace-relative path, refusing anything outside the workspace."""
        if not relative or "\x00" in relative:
            raise ValueError("empty path")
        path = (self.workspace / relative).resolve()
        if path != self.workspace and self.workspace not in path.parents:
            raise PermissionError(f"{relative} is outside the workspace")
        if must_exist and not path.exists():
            raise FileNotFoundError(relative)
        return path

    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.workspace).as_posix()


def run_worker(request: Dict[str, Any], cwd: Path) -> Dict[str, Any]:
    env = dict(os.environ)
    package_root = str(HERE.parent.parent)
    env["PYTHONPATH"] = package_root + os.pathsep + env.get("PYTHONPATH", "")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pythonfmu3.studio.worker"], input=json.dumps(request),
            capture_output=True, text=True, timeout=WORKER_TIMEOUT, cwd=str(cwd), env=env,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timed out after {WORKER_TIMEOUT} s"}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "The worker process failed", "traceback": (proc.stdout + proc.stderr)[-8000:]}


def environment() -> Dict[str, Any]:
    from .worker import find_fmusim

    def has(module):
        import importlib.util
        return importlib.util.find_spec(module) is not None

    return {
        "version": __version__,
        "python": sys.version.split()[0],
        "fmusim": find_fmusim(),
        "fmpy": has("fmpy"),
        "numpy": has("numpy"),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = f"PythonFMU3Studio/{__version__}"
    state: StudioState  # set on the class by serve()

    # -- plumbing ---------------------------------------------------------------------------

    def log_message(self, fmt, *args):  # keep the terminal quiet
        if os.environ.get("PYTHONFMU3_STUDIO_DEBUG"):
            super().log_message(fmt, *args)

    def _send(self, status: int, body: bytes, content_type: str, extra: Optional[Dict[str, str]] = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: Any, status: int = 200):
        self._send(status, json.dumps(payload, default=str).encode("utf-8"), "application/json; charset=utf-8")

    def _error(self, status: int, message: str, detail: str = ""):
        self._json({"ok": False, "error": message, "traceback": detail}, status)

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        return host in ("127.0.0.1", "localhost", "::1")

    def _token_ok(self, query: Dict[str, list]) -> bool:
        supplied = self.headers.get("X-Studio-Token") or (query.get("token") or [""])[0]
        return secrets.compare_digest(supplied, self.state.token)

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_UPLOAD:
            raise ValueError("Upload too large")
        return self.rfile.read(length) if length else b""

    def _json_body(self) -> Dict[str, Any]:
        data = self._body()
        return json.loads(data or b"{}")

    # -- routing ----------------------------------------------------------------------------

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def _dispatch(self, method: str):
        if not self._host_ok():
            return self._error(HTTPStatus.FORBIDDEN, "Invalid Host header")
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if method == "GET" and not url.path.startswith("/api/"):
            return self._static(url.path)
        if not self._token_ok(query):
            return self._error(HTTPStatus.FORBIDDEN, "Missing or invalid token")
        route = getattr(self, f"api_{method.lower()}_{url.path[5:].replace('/', '_')}", None)
        if route is None:
            return self._error(HTTPStatus.NOT_FOUND, f"No such endpoint: {url.path}")
        try:
            route(query)
        except (FileNotFoundError, PermissionError, ValueError, KeyError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, f"{type(exc).__name__}: {exc}")
        except Exception as exc:  # pragma: no cover - unexpected
            import traceback
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"{type(exc).__name__}: {exc}", traceback.format_exc())

    def _static(self, path: str):
        name = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (STATIC / name).resolve()
        if STATIC.resolve() not in target.parents or not target.is_file():
            return self._error(HTTPStatus.NOT_FOUND, "Not found")
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        csp = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
               "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self._send(200, target.read_bytes(), ctype, {"Content-Security-Policy": csp})

    # -- API: environment and files ---------------------------------------------------------

    def api_get_env(self, query):
        info = environment()
        info["workspace"] = str(self.state.workspace)
        self._json({"ok": True, "result": info})

    def api_get_files(self, query):
        files = []
        skip = {".git", "__pycache__", ".venv", "venv", "node_modules"}
        for path in sorted(self.state.workspace.rglob("*")):
            rel = path.relative_to(self.state.workspace)
            if any(part in skip or part.startswith(".") for part in rel.parts[:-1]):
                continue
            if path.is_file() and path.suffix in (".py", ".fmu"):
                files.append({"path": rel.as_posix(), "kind": path.suffix[1:], "size": path.stat().st_size})
            if len(files) >= 500:
                break
        self._json({"ok": True, "result": files})

    def api_get_file(self, query):
        path = self.state.resolve(query["path"][0])
        if path.suffix != ".py":
            raise ValueError("Only .py files can be opened in the editor")
        self._json({"ok": True, "result": {"path": self.state.rel(path), "content": path.read_text(encoding="utf-8")}})

    def api_post_file(self, query):
        body = self._json_body()
        path = self.state.resolve(body["path"], must_exist=False)
        if path.suffix != ".py":
            raise ValueError("Only .py files can be saved")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body["content"], encoding="utf-8")
        self._json({"ok": True, "result": {"path": self.state.rel(path)}})

    # -- API: model operations (worker process) ---------------------------------------------

    def _model_request(self, command: str, body: Dict[str, Any]):
        path = self.state.resolve(body["path"])
        request = dict(body, command=command, path=str(path))
        return path, run_worker(request, path.parent)

    def api_post_analyze(self, query):
        _, response = self._model_request("analyze", self._json_body())
        self._json(response)

    def api_post_simulate(self, query):
        _, response = self._model_request("simulate", self._json_body())
        self._json(response)

    def api_post_build(self, query):
        body = self._json_body()
        path = self.state.resolve(body["path"])
        response = run_worker({"command": "build", "path": str(path),
                               "dest": str(path.parent / "build")}, path.parent)
        if response.get("ok"):
            fmu = Path(response["result"]["fmu"])
            response["result"]["fmu"] = self.state.rel(fmu)
            self.state.last_build[self.state.rel(path)] = self.state.rel(fmu)
        self._json(response)

    def api_post_validate(self, query):
        body = self._json_body()
        fmu = self.state.resolve(body["fmu"])
        self._json(run_worker({"command": "validate", "fmu": str(fmu)}, self.state.workspace))

    def api_get_download(self, query):
        path = self.state.resolve(query["path"][0])
        if path.suffix != ".fmu":
            raise ValueError("Only FMUs can be downloaded")
        self._send(200, path.read_bytes(), "application/octet-stream",
                   {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(path.name)}"})

    def api_post_inspect(self, query):
        if (self.headers.get("Content-Type") or "").startswith("application/json"):
            body = self._json_body()
            fmu = self.state.resolve(body["path"])
            name = fmu.name
        else:
            name = re.sub(r"[^A-Za-z0-9._-]", "_", (query.get("name") or ["upload.fmu"])[0]) or "upload.fmu"
            fmu = self.state.uploads / secrets.token_hex(8) / name
            fmu.parent.mkdir(parents=True)
            fmu.write_bytes(self._body())
        response = run_worker({"command": "inspect", "path": str(fmu), "name": name}, self.state.workspace)
        if response.get("ok") and environment()["fmusim"]:
            response["result"]["validation"] = run_worker({"command": "validate", "fmu": str(fmu)},
                                                          self.state.workspace).get("result")
        self._json(response)

    # -- API: templates -----------------------------------------------------------------------

    def api_get_templates(self, query):
        items = []
        for key, (title, iface, cats, desc, tags) in TEMPLATE_INFO.items():
            if (TEMPLATES / f"{key}.py").exists():
                items.append({"id": key, "title": title, "interface": iface, "categories": cats.split(),
                              "description": desc, "tags": tags})
        self._json({"ok": True, "result": items})

    def api_post_templates_use(self, query):
        body = self._json_body()
        key = body["id"]
        if key not in TEMPLATE_INFO:
            raise KeyError(key)
        target = self.state.resolve(body.get("name") or f"{key}.py", must_exist=False)
        if target.suffix != ".py":
            raise ValueError("The file name must end in .py")
        if target.exists():
            raise ValueError(f"{self.state.rel(target)} already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TEMPLATES / f"{key}.py", target)
        self._json({"ok": True, "result": {"path": self.state.rel(target)}})


def serve(workspace: Path, port: int = 0, open_browser: bool = True) -> ThreadingHTTPServer:
    state = StudioState(workspace)
    handler = type("StudioHandler", (Handler,), {"state": state})
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    httpd.studio_state = state
    url = f"http://127.0.0.1:{httpd.server_address[1]}/?token={state.token}"
    httpd.studio_url = url
    if open_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    return httpd


def main(folder: str = ".", port: int = 0, no_browser: bool = False, **_):
    workspace = Path(folder).resolve()
    if not workspace.is_dir():
        raise SystemExit(f"{workspace} is not a folder")
    httpd = serve(workspace, port, open_browser=not no_browser)
    print(f"PythonFMU3 Studio {__version__}")
    print(f"  workspace: {workspace}")
    print(f"  open:      {httpd.studio_url}")
    print("  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        shutil.rmtree(httpd.studio_state.uploads, ignore_errors=True)


def create_command_parser(parser: argparse.ArgumentParser):
    parser.add_argument("folder", nargs="?", default=".", help="Workspace folder with your model scripts (default: current folder).")
    parser.add_argument("-p", "--port", type=int, default=0, help="Port to listen on (default: a free port).")
    parser.add_argument("--no-browser", action="store_true", help="Don't open a browser window.")
    parser.set_defaults(execute=main)


if __name__ == "__main__":
    p = argparse.ArgumentParser(prog="pythonfmu3 studio")
    create_command_parser(p)
    args = vars(p.parse_args())
    args.pop("execute")(**args)
