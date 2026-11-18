"""Tests for the MCP server (pythonfmu3 mcp), over a real stdio connection."""
import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")
from mcp.client.session import ClientSession                     # noqa: E402
from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402

from pythonfmu3.builder import FmuBuilder                         # noqa: E402
from pythonfmu3.mcp_server import Workspace                       # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def _attr(obj, *names):
    for n in names:                       # mcp 2 uses snake_case, mcp 1 camelCase
        if hasattr(obj, n):
            return getattr(obj, n)
    return None


def _payload(result):
    structured = _attr(result, "structured_content", "structuredContent")
    if structured:
        return structured["result"] if list(structured) == ["result"] else structured
    text = result.content[0].text
    return json.loads(text) if text[:1] in "{[" else text


def run_session(workspace, steps):
    async def main():
        env = dict(os.environ, PYTHONPATH=str(REPO) + os.pathsep + os.environ.get("PYTHONPATH", ""))
        params = StdioServerParameters(command=sys.executable, env=env,
                                       args=["-m", "pythonfmu3", "mcp", str(workspace)])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                async def call(tool, **args):
                    result = await session.call_tool(tool, args)
                    return bool(_attr(result, "is_error", "isError")), _payload(result)
                return await steps(session, call)
    return asyncio.run(main())


def test_workspace_paths(tmp_path):
    (tmp_path / "ws").mkdir()
    ws = Workspace(tmp_path / "ws")
    assert ws.path("a.py", must_exist=False) == (tmp_path / "ws" / "a.py").resolve()
    with pytest.raises(PermissionError):
        ws.path("../x.py", must_exist=False)
    with pytest.raises(PermissionError):
        ws.path("/etc/passwd")


TANK = """from pythonfmu3 import Fmi3Causality, Fmi3Slave, Fmi3Variability, Float64


class Tank(Fmi3Slave):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.time = 0.0
        self.q_in = 0.5
        self.level = 1.0
        self.register_variable(Float64("time", causality=Fmi3Causality.independent,
                                       variability=Fmi3Variability.continuous))
        self.register_variable(Float64("q_in", causality=Fmi3Causality.input, start=0.5))
        self.register_variable(Float64("level", causality=Fmi3Causality.output))

    def do_step(self, current_time, step_size):
        self.level += self.q_in * step_size
        self.time = current_time + step_size
        return True
"""


def test_write_check_simulate_build(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()

    async def steps(session, call):
        tools = {t.name for t in (await session.list_tools()).tools}
        assert {"get_guide", "list_files", "read_file", "write_model", "edit_model", "copy_template", "run_checks",
                "simulate", "build_fmu", "inspect_fmu", "validate_fmu", "list_templates", "read_template"} == tools

        err, bad = await call("write_model", path="bad.py", content="x = 1\n")
        assert not err and bad["ok"] is False

        err, model = await call("write_model", path="tank.py", content=TANK)
        assert not err and model["problems"] == [] and len(model["variables"]) == 3

        err, sim = await call("simulate", path="tank.py", stop_time=2.0, start_values={"q_in": 1.0})
        assert not err and sim["variables"]["level"]["final"] == pytest.approx(3.0)
        assert (workspace / sim["csv"]).exists()

        if FmuBuilder.has_binary():
            err, built = await call("build_fmu", path="tank.py")
            assert not err and built["fmu"] == "build/Tank.fmu" and built["platforms"]
            err, info = await call("inspect_fmu", path="build/Tank.fmu")
            assert not err and info["ok"]
            err, valid = await call("validate_fmu", path="build/Tank.fmu")
            assert not err and valid["passed"]

        err, files = await call("list_files")
        assert any(f.startswith("tank.py") for f in files["files"])

        err, msg = await call("write_model", path="../escape.py", content="x = 1\n")
        assert err and "outside the workspace" in str(msg)
        err, msg = await call("read_file", path="/etc/passwd")
        assert err
    run_session(workspace, steps)
    assert not (tmp_path / "escape.py").exists()


def test_templates_edits_and_summaries(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()

    async def steps(session, call):
        err, copied = await call("copy_template", name="bouncing_ball")
        assert not err and copied["saved"] == "bouncing_ball.py" and copied["problems"] == []
        assert "class BouncingBall" in copied["content"]
        err, again = await call("copy_template", name="bouncing_ball")
        assert not err and again["saved"] == "bouncing_ball_2.py"

        err, edited = await call("edit_model", path="bouncing_ball.py", old_text="self.e = 0.7",
                                 new_text="self.e = 0.5")
        assert not err and edited["replacements"] == 1 and edited["problems"] == []
        assert "self.e = 0.5" in (workspace / "bouncing_ball.py").read_text()

        err, msg = await call("edit_model", path="bouncing_ball.py", old_text="not in the file", new_text="x")
        assert err and "not found" in str(msg)
        err, msg = await call("edit_model", path="bouncing_ball.py", old_text="self.", new_text="self.")
        assert err and "occurs" in str(msg)

        err, sim = await call("simulate", path="bouncing_ball.py", stop_time=3.0)
        assert not err and set(sim["variables"]) == {"ball.h", "ball.v"}
        assert "not_shown" in sim and sim["events"] > 0
        err, sim = await call("simulate", path="bouncing_ball.py", stop_time=3.0, variables=["ball.derv"])
        assert not err and set(sim["variables"]) == {"ball.derv"}
    run_session(workspace, steps)


ARRAYS = """import numpy as np
from pythonfmu3 import Dimension, Fmi3Causality, Fmi3Slave, Fmi3Variability, Float64


class Profile(Fmi3Slave):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.time = 0.0
        self.gain = 1.0
        self.T = np.arange(100, dtype=float)
        self.total = 0.0
        self.register_variable(Float64("time", causality=Fmi3Causality.independent,
                                       variability=Fmi3Variability.continuous))
        self.register_variable(Float64("gain", causality=Fmi3Causality.parameter,
                                       variability=Fmi3Variability.tunable, start=1.0))
        self.register_variable(Float64("T", causality=Fmi3Causality.output, dimensions=[Dimension(start="100")]))
        self.register_variable(Float64("total", causality=Fmi3Causality.output))

    def do_step(self, current_time, step_size):
        self.T = self.gain * np.arange(100, dtype=float)
        self.total = float(self.T.sum())
        self.time = current_time + step_size
        return True
"""


def test_array_outputs_and_start_values(tmp_path):
    pytest.importorskip("numpy")
    workspace = tmp_path / "ws"
    workspace.mkdir()

    async def steps(session, call):
        err, model = await call("write_model", path="profile.py", content=ARRAYS)
        assert not err and model["problems"] == []
        err, sim = await call("simulate", path="profile.py", stop_time=1.0, start_values={"gain": 2.0})
        assert not err
        # scalars are summarised even when a long array comes first
        assert sim["variables"]["total"]["final"] == pytest.approx(2.0 * sum(range(100)))
        # the whole array is recorded and summarised as a profile
        profile = sim["variables"]["T"]
        assert profile["elements"] == 100
        assert profile["final_sampled"]["[100]"] == pytest.approx(198.0)
        header = (workspace / sim["csv"]).read_text().split("\n", 1)[0]
        assert "T[100]" in header
        # a misspelt start value is an error, not silently ignored
        err, msg = await call("simulate", path="profile.py", stop_time=1.0, start_values={"gian": 2.0})
        assert msg["ok"] is False and "Unknown variable 'gian'" in msg["error"]
    run_session(workspace, steps)
