"""Tests for the Jupyter support (pythonfmu3.notebook): the %%fmu magic, Model and FMU."""
import json
import os
from pathlib import Path

import pytest

import pythonfmu3
from pythonfmu3.builder import FmuBuilder
from pythonfmu3.notebook import FMU, MARKER, Model, fmu_cell

NOTEBOOK = Path(__file__).resolve().parents[2] / "examples" / "notebooks" / "getting_started.ipynb"

TANK = """class Tank(Fmi3Slave):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.description = "A <tank> & more"
        self.time = 0.0
        self.q_in = 0.2
        self.area = 2.0
        self.level = 1.0
        self.register_units([Unit(name="m", m=1)])
        self.register_variable(Float64("time", causality=Fmi3Causality.independent,
                                       variability=Fmi3Variability.continuous))
        self.register_variable(Float64("q_in", causality=Fmi3Causality.input, start=0.2))
        self.register_variable(Float64("area", causality=Fmi3Causality.parameter,
                                       variability=Fmi3Variability.tunable, start=2.0))
        self.register_variable(Float64("level", causality=Fmi3Causality.output, unit="m"))

    def do_step(self, current_time, step_size):
        self.level += self.q_in / self.area * step_size
        self.time = current_time + step_size
        return True
"""


@pytest.fixture
def in_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_cell_magic_writes_checks_and_binds(in_tmp):
    ns = {}
    model = fmu_cell("", TANK, ns)
    assert ns["Tank"] is model
    assert model.ok and model.problems == []
    text = (in_tmp / "tank.py").read_text()
    assert text.startswith("from pythonfmu3 import *  " + MARKER + "\nclass Tank")
    assert [v["name"] for v in model.variables] == ["time", "q_in", "area", "level"]
    assert repr(model) == "<Model Tank (tank.py): 4 variables, no problems>"


def test_cell_magic_options_and_errors(in_tmp):
    model = fmu_cell("models/my_tank.py", "from pythonfmu3 import *\n" + TANK, {})
    assert model.path == (in_tmp / "models" / "my_tank.py").resolve()
    assert model.path.read_text().startswith(MARKER + "\nfrom pythonfmu3 import *")

    broken = fmu_cell("oops.py", "class Oops(Fmi3Slave)\n    pass\n", {})
    assert not broken.ok
    assert "line 2" in broken.problems[0]           # cell line 1 + the header line
    assert "SyntaxError" in broken._repr_html_()

    (in_tmp / "mine.py").write_text("x = 1\n")
    with pytest.raises(FileExistsError):
        fmu_cell("mine.py", TANK, {})
    assert fmu_cell("mine.py --overwrite", TANK, {}).ok
    with pytest.raises(ValueError, match="no model class"):
        fmu_cell("", "x = 1\n", {})


def test_problems_are_reported(in_tmp):
    model = fmu_cell("bad.py", "class Bad(Fmi3Slave):\n    def __init__(self, **kw):\n        super().__init__(**kw)\n"
                     "        self.register_variable(Float64('u', causality=Fmi3Causality.input))\n", {})
    assert not model.ok
    assert any("Independent variable" in p for p in model.problems)
    assert "Independent variable" in model._repr_html_()


def test_html_is_escaped(in_tmp):
    html = fmu_cell("", TANK, {})._repr_html_()
    assert "q_in" in html and "area = 2.0" in html and "level [m]" in html
    assert "<tank>" not in html


def test_simulate_returns_a_dataframe(in_tmp):
    pd = pytest.importorskip("pandas")
    model = fmu_cell("", TANK, {})
    res = model.simulate(stop_time=10, start_values={"q_in": 0.4})
    assert isinstance(res, pd.DataFrame) and res.index.name == "time"
    assert list(res.columns) == ["level"] and len(res) == 501
    assert res["level"].iloc[-1] == pytest.approx(3.0)
    assert res.attrs["simulator"] == "python"
    with pytest.raises(ValueError, match="Unknown variable"):
        model.simulate(stop_time=1, start_values={"nope": 1})


def test_model_exchange_events(in_tmp):
    pytest.importorskip("pandas")
    from pythonfmu3.studio.server import TEMPLATES
    model = fmu_cell("", (TEMPLATES / "bouncing_ball.py").read_text(), {})
    res = model.simulate(stop_time=3)
    assert res.attrs["interface"] == "me" and len(res.attrs["events"]) > 3


@pytest.mark.skipif(not FmuBuilder.has_binary(), reason="needs the compiled wrapper")
def test_build_and_inspect(in_tmp):
    fmu = fmu_cell("", TANK, {}).build()
    assert isinstance(fmu, FMU) and fmu.path.name == "Tank.fmu"
    assert fmu.info["platforms"] and fmu.info["interfaces"] == ["CoSimulation"]
    assert "Tank.fmu" in repr(fmu) and "q_in" in fmu._repr_html_()
    assert fmu.validate()["passed"]
    assert repr(FMU(fmu.path)) == repr(fmu)


def test_ipython_extension_registers_the_magic(in_tmp):
    class Shell:
        user_ns = {}
        registered = None

        def register_magic_function(self, func, magic_kind, magic_name):
            self.registered = (func, magic_kind, magic_name)

    shell = Shell()
    pythonfmu3.load_ipython_extension(shell)
    func, kind, name = shell.registered
    assert (kind, name) == ("cell", "fmu")
    model = func("", TANK)
    assert shell.user_ns["Tank"] is model


@pytest.mark.skipif(not NOTEBOOK.exists(), reason="needs a source checkout")
def test_example_notebook_runs(in_tmp):
    """Run the example notebook's code cells, emulating the two IPython magics it uses."""
    pytest.importorskip("pandas")
    pytest.importorskip("matplotlib")
    os.environ.setdefault("MPLBACKEND", "Agg")
    ns = {"__name__": "__main__"}
    for cell in json.loads(NOTEBOOK.read_text())["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        if source.startswith("%%fmu"):
            line, body = source.split("\n", 1)
            fmu_cell(line[len("%%fmu"):].strip(), body, ns)
            continue
        lines = [ln for ln in source.splitlines() if not ln.startswith("%load_ext")]
        if "Tank.build()" in source and not FmuBuilder.has_binary():
            continue
        if "FMU(" in source and not (in_tmp / "Tank.fmu").exists():
            continue
        exec(compile("\n".join(lines), "cell", "exec"), ns)
    final = ns["sweep"].iloc[-1]
    for column, value in final.items():
        valve = float(column.split("=")[1])
        assert value == pytest.approx((0.05 / valve) ** 2, rel=0.05)
