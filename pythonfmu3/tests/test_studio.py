"""Tests for PythonFMU3 Studio (pythonfmu3 studio): the worker and the HTTP API."""
import json
import shutil
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pytest

from pythonfmu3.builder import FmuBuilder
from pythonfmu3.studio import server as studio
from pythonfmu3.studio.server import TEMPLATE_INFO, TEMPLATES, run_worker

HERE = Path(__file__).parent


def worker(command, **kwargs):
    response = run_worker(dict(kwargs, command=command), HERE)
    assert response["ok"], response.get("traceback") or response.get("error")
    return response["result"]


@pytest.mark.parametrize("template", sorted(TEMPLATE_INFO))
def test_templates_are_clean_models(template):
    result = worker("analyze", path=str(TEMPLATES / f"{template}.py"))
    problems = [c for c in result["checks"] if c["level"] != "ok"]
    assert not problems, problems
    assert result["interfaces"]


def test_analyze_reports_variables_and_problems(tmp_path):
    script = tmp_path / "bad.py"
    script.write_text(
        "from pythonfmu3 import Fmi3Slave, Fmi3Causality, Float64, Int32\n"
        "class Bad(Fmi3Slave):\n"
        "    author = 'class level'\n"
        "    def __init__(self, **kwargs):\n"
        "        super().__init__(**kwargs)\n"
        "        self.register_variable(Float64('u', causality=Fmi3Causality.input))\n"   # no attribute yet
        "        self.u = 1.0\n"
        "        self.n = 0\n"
        "        self.register_variable(Int32('n', causality=Fmi3Causality.output))\n"
        "    def do_step(self, t, dt):\n"
        "        return True\n"
    )
    result = worker("analyze", path=str(script))
    titles = " | ".join(c["title"] for c in result["checks"])
    assert "Independent variable" in titles
    assert "u: not settable" in titles
    assert "n: variability" in titles
    assert "Class attribute 'author' is ignored" in titles
    assert [v["name"] for v in result["variables"]] == ["u", "n"]
    assert "<ModelVariables>" in result["xml"]


def test_simulate_cosimulation_and_model_exchange():
    cs = worker("simulate", path=str(TEMPLATES / "dahlquist.py"), interface="cs", stopTime=1.0, stepSize=0.1)
    assert cs["series"]["x"][-1] == pytest.approx(0.9 ** 10)            # explicit Euler in do_step
    me = worker("simulate", path=str(TEMPLATES / "dahlquist.py"), interface="me", stopTime=1.0, stepSize=0.1)
    assert me["series"]["x"][-1] == pytest.approx(0.36787944, rel=1e-6)  # exp(-1), RK4
    ball = worker("simulate", path=str(TEMPLATES / "bouncing_ball.py"), stopTime=1.0, stepSize=0.01)
    assert ball["events"][0]["t"] == pytest.approx((2 / 9.81) ** 0.5, rel=1e-6)


def test_simulate_uses_start_values():
    result = worker("simulate", path=str(TEMPLATES / "signal_generator.py"), stopTime=1.0, stepSize=0.25,
                    startValues={"mode": 2, "amplitude": 3})
    assert max(result["series"]["y"]) <= 3.0 and min(result["series"]["y"]) >= -3.0
    assert result["series"]["y"][1] == pytest.approx(3 * (2 * 0.125 - 1))


@pytest.mark.skipif(not FmuBuilder.has_binary(), reason="needs the compiled wrapper")
def test_build_and_inspect(tmp_path):
    script = tmp_path / "pid.py"
    shutil.copy(TEMPLATES / "pid_controller.py", script)
    built = worker("build", path=str(script), dest=str(tmp_path / "out"))
    assert Path(built["fmu"]).exists() and built["platforms"]
    info = worker("inspect", path=built["fmu"])
    assert info["modelName"] == "PIDController"
    assert info["fmiVersion"] == "3.0" and info["interfaces"] == ["CoSimulation"]
    assert not info["problems"]
    assert {v["name"] for v in info["variables"]} >= {"setpoint", "measurement", "output", "Kp"}


@pytest.fixture()
def app(tmp_path):
    shutil.copy(TEMPLATES / "dahlquist.py", tmp_path / "model.py")
    httpd = studio.serve(tmp_path, port=0, open_browser=False)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd, tmp_path
    httpd.shutdown()
    httpd.server_close()


def call(httpd, path, body=None, token=True, host=None):
    port = httpd.server_address[1]
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None)
    if token:
        req.add_header("X-Studio-Token", httpd.studio_state.token)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if host:
        req.add_header("Host", host)
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def test_api_requires_token_and_local_host(app):
    httpd, _ = app
    assert call(httpd, "/api/env", token=False)[0] == 403
    assert call(httpd, "/api/env", host="attacker.example")[0] == 403
    status, body = call(httpd, "/api/env")
    assert status == 200 and json.loads(body)["ok"]


def test_api_stays_inside_the_workspace(app):
    httpd, _ = app
    assert call(httpd, "/api/file?path=../outside.py")[0] == 400
    assert call(httpd, "/api/file", {"path": "../escape.py", "content": "x"})[0] == 400


def test_api_round_trip(app):
    httpd, ws = app
    status, body = call(httpd, "/api/files")
    assert [f["path"] for f in json.loads(body)["result"]] == ["model.py"]
    status, body = call(httpd, "/api/file?path=model.py")
    content = json.loads(body)["result"]["content"]
    assert "class Dahlquist" in content
    assert call(httpd, "/api/file", {"path": "model.py", "content": content.replace("self.k = 1.0", "self.k = 2.0")})[0] == 200
    status, body = call(httpd, "/api/analyze", {"path": "model.py"})
    k = next(v for v in json.loads(body)["result"]["variables"] if v["name"] == "k")
    assert k["start"] == 2.0
    status, body = call(httpd, "/api/templates/use", {"id": "thermostat", "name": "room.py"})
    assert json.loads(body)["result"]["path"] == "room.py" and (ws / "room.py").exists()
    assert call(httpd, "/api/templates/use", {"id": "thermostat", "name": "room.py"})[0] == 400   # no overwrite


def test_static_page_is_served(app):
    httpd, _ = app
    status, body = call(httpd, "/", token=False)
    assert status == 200 and b"PythonFMU3 Studio" in body
    assert call(httpd, "/../server.py", token=False)[0] == 404
