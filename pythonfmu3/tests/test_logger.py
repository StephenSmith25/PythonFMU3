import sys
import itertools
import pytest
from unittest.mock import call, MagicMock

from pythonfmu3.builder import FmuBuilder
from pythonfmu3.enums import Fmi3Status
from pythonfmu3.fmi3slave import Fmi3Slave

fmpy = pytest.importorskip(
    "fmpy", reason="fmpy is not available for testing the produced FMU"
)
pytestmark = pytest.mark.skipif(
    not FmuBuilder.has_binary(), reason="No binary available for the current platform."
)

if True:
    pytest.skip("This test needs to be manually enabled", allow_module_level=True)


@pytest.mark.integration
@pytest.mark.parametrize("debug_logging", [True, False])
def test_logger(tmp_path, debug_logging):
    name = "PythonSlaveWithDebugLogger" if debug_logging else "PythonSlaveWithLogger"
    category = "category"
    message = "log message"

    log_calls = [
        (
            f"{status.name.upper()} - {debug} - {message}", 
            status, 
            category, 
            debug
        ) for debug, status in itertools.product([True, False], Fmi3Status)
    ]

    fmu_calls = "\n".join([
        '        self.log("{}", Fmi3Status.{}, "{}", {})'.format(c[0], c[1].name, c[2], c[3]) for c in log_calls
    ])

    slave_code = f"""from pythonfmu3.Fmi3Slave import Fmi3Slave, Fmi3Status, Fmi3Causality, Int32, Float64, Boolean, String


class {name}(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.realIn = 22.0
        self.realOut = 0.0
        self.register_variable(Float64("realIn", causality=Fmi3Causality.input))
        self.register_variable(Float64("realOut", causality=Fmi3Causality.output))


    def do_step(self, current_time, step_size):
{fmu_calls}
        return True
"""

    script_file = tmp_path / "orig" / f"{name.lower()}.py"
    script_file.parent.mkdir(parents=True, exist_ok=True)
    script_file.write_text(slave_code)

    fmu = FmuBuilder.build_FMU(script_file, dest=tmp_path)
    assert fmu.exists()

    logger = MagicMock()

    fmpy.simulate_fmu(
        str(fmu),
        stop_time=1e-3,
        output_interval=1e-3,
        logger=logger,
        debug_logging=debug_logging
    )

    expected_calls = [
        call(
            logger.call_args[0][0],  # Don't test the first argument
            bytes(name, encoding="utf-8"),
            int(c[1]),
            bytes(c[2], encoding="utf-8"),
            bytes(c[0], encoding="utf-8")
        ) for c in filter(lambda c: debug_logging or not c[3], log_calls)
    ]
    
    assert logger.call_count == len(Fmi3Status) * (1 + int(debug_logging))
    logger.assert_has_calls(expected_calls)


@pytest.mark.integration
@pytest.mark.parametrize("debug_logging", [True, False])
@pytest.mark.parametrize("categories", [(), ("logStatusError", "logStatusFatal")])
def test_log_categories(tmp_path, debug_logging, categories):
    name = "PythonSlaveDebugCategories" if debug_logging else "PythonSlaveCategories"
    message = "log message"

    log_calls = [
        (
            f"{status.name.upper()} - {debug} - {message}", 
            status,
            debug
        ) for debug, status in itertools.product([True, False], Fmi3Status)
    ]

    fmu_calls = "\n".join([
        '        self.log("{}", Fmi3Status.{}, None, {})'.format(c[0], c[1].name, c[2]) for c in log_calls
    ])

    slave_code = f"""from pythonfmu3.Fmi3Slave import Fmi3Slave, Fmi3Status, Fmi3Causality, Int32, Float64, Boolean, String


class {name}(Fmi3Slave):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.realIn = 22.0
        self.realOut = 0.0
        self.register_variable(Float64("realIn", causality=Fmi3Causality.input))
        self.register_variable(Float64("realOut", causality=Fmi3Causality.output))


    def do_step(self, current_time, step_size):
{fmu_calls}
        return True
"""

    script_file = tmp_path / "orig" / f"{name.lower()}.py"
    script_file.parent.mkdir(parents=True, exist_ok=True)
    script_file.write_text(slave_code)

    fmu = FmuBuilder.build_FMU(script_file, dest=tmp_path)
    assert fmu.exists()

    logger = MagicMock()

    # Load the model
    callbacks = fmpy.fmi3.fmi3CallbackFunctions()
    callbacks.logger = fmpy.fmi3.fmi3CallbackLoggerTYPE(logger)
    callbacks.allocateMemory = fmpy.fmi3.fmi3CallbackAllocateMemoryTYPE(fmpy.calloc)
    callbacks.freeMemory = fmpy.fmi3.fmi3CallbackFreeMemoryTYPE(fmpy.free)

    model_description = fmpy.read_model_description(fmu)
    unzip_dir = fmpy.extract(fmu)

    model = fmpy.fmi3.FMI3Slave(
        guid=model_description.guid,
        unzipDirectory=unzip_dir,
        modelIdentifier=model_description.coSimulation.modelIdentifier,
        instanceName='instance1')
    # Instantiate the model
    model.instantiate(callbacks=callbacks)
    model.setDebugLogging(debug_logging, categories)
    model.setupExperiment()
    model.enterInitializationMode()
    model.exitInitializationMode()
    # Execute the model
    model.doStep(0., 0.1)
    # Clean the model
    model.terminate()

    expected_calls = []
    for c in filter(lambda c: debug_logging or not c[2], log_calls):
        category = f"logStatus{c[1].name.capitalize()}"
        if category not in Fmi3Slave.log_categories:
            category = "logAll"
        if len(categories) == 0 or category in categories:
            expected_calls.append(call(
                logger.call_args[0][0],  # Don't test the first argument
                b'instance1',
                int(c[1]),
                bytes(category, encoding="utf-8"),
                bytes(c[0], encoding="utf-8")
            ))

    n_calls = len(Fmi3Status) if len(categories) == 0 else len(categories)

    assert logger.call_count == n_calls * (1 + int(debug_logging))
    logger.assert_has_calls(expected_calls)
