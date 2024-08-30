import math
import pytest

from pythonfmu3.builder import FmuBuilder

pytestmark = pytest.mark.skipif(
    not FmuBuilder.has_binary(), reason="No binary available for the current platform."
)

fmpy = pytest.importorskip(
    "fmpy", reason="fmpy is not available for testing the produced FMU"
)


def mapped(md):
    m = {}
    for v in md.modelVariables:
        m[v.name] = v
    return m


@pytest.mark.integration
def test_integration_multiple_fmus(tmp_path):
    slave1_code = """import math
from pythonfmu3 import Fmi3Slave, Fmi3Causality, Fmi3Variability, Int32, Float64, Boolean, String


class Slave1(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.realIn = 22.0
        self.realOut = 0.0
        self.time = 0
        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(Float64("realIn", causality=Fmi3Causality.input))
        self.register_variable(Float64("realOut", causality=Fmi3Causality.output))

    def do_step(self, current_time, step_size):
        self.log("Do step on Slave1.")
        self.realOut = self.realIn * 5.0 * (1.0 - math.exp(-1.0 * (current_time + step_size) / 0.1))
        return True
"""

    slave2_code = """from pythonfmu3 import Fmi3Slave, Fmi3Causality, Fmi3Variability, Int32, Float64, Boolean, String


class Slave2(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.realIn = 22.0
        self.realOut = 0.0
        self.time = 0
        self.register_variable(Float64("time", causality=Fmi3Causality.independent, variability=Fmi3Variability.continuous))
        self.register_variable(Float64("realIn", causality=Fmi3Causality.input))
        self.register_variable(Float64("realOut", causality=Fmi3Causality.output))

    def do_step(self, current_time, step_size):
        self.log("Do step on Slave2.")
        self.realOut = -2.0 * self.realIn
        return True
"""

    script1_file = tmp_path / "orig" / "slave1.py"
    script1_file.parent.mkdir(parents=True, exist_ok=True)
    script1_file.write_text(slave1_code)

    fmu1 = FmuBuilder.build_FMU(
        script1_file,
        dest=tmp_path,
        needsExecutionTool="false"
    )
    assert fmu1.exists()

    script2_file = tmp_path / "orig" / "slave2.py"
    script2_file.write_text(slave2_code)

    fmu2 = FmuBuilder.build_FMU(
        script2_file,
        dest=tmp_path,
        needsExecutionTool="false"
    )
    assert fmu2.exists()

    md1 = fmpy.read_model_description(fmu1)
    unzip_dir = fmpy.extract(fmu1)

    model1 = fmpy.fmi3.FMU3Slave(
        guid=md1.guid,
        unzipDirectory=unzip_dir,
        modelIdentifier=md1.coSimulation.modelIdentifier,
        instanceName='instance1')

    model1.instantiate()
    model1.enterInitializationMode()
    model1.exitInitializationMode()

    md2 = fmpy.read_model_description(fmu2)
    unzip_dir = fmpy.extract(fmu2)

    model2 = fmpy.fmi3.FMU3Slave(
        guid=md2.guid,
        unzipDirectory=unzip_dir,
        modelIdentifier=md2.coSimulation.modelIdentifier,
        instanceName='instance2')

    variables1 = mapped(md1)
    variables2 = mapped(md2)

    realOut = variables1["realOut"]
    realIn = variables2["realIn"]

    model2.instantiate()
    model2.enterInitializationMode()

    value = model1.getFloat64([realOut.valueReference])[0]
    model2.setFloat64([realIn.valueReference], [value])

    model2.exitInitializationMode()

    time = 0
    stop_time = 0.1
    step_size = 0.025

    while time < stop_time:

        model2.setFloat64([realIn.valueReference], [value])

        model1.doStep(time, step_size)
        model2.doStep(time, step_size)

        value = model1.getFloat64([realOut.valueReference])[0]

        time += step_size

    assert value == pytest.approx(
        22.0 * 5.0 * (1.0 - math.exp(-1.0 * time / 0.1)), rel=1e-7
    )
