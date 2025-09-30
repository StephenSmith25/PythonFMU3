import math
from pathlib import Path
import ctypes

import pytest

from pythonfmu3.builder import FmuBuilder

pytestmark = pytest.mark.skipif(
    not FmuBuilder.has_binary(), reason="No binary available for the current platform."
)
fmpy = pytest.importorskip(
    "fmpy", reason="fmpy is required for testing the produced FMU"
)


def mapped(md):
    m = {}
    for v in md.modelVariables:
        m[v.name] = v
    return m


@pytest.mark.integration
def test_integration_demo(tmp_path):
    script_file = Path(__file__).parent / "slaves/pythonslave.py"
    fmu = FmuBuilder.build_FMU(script_file, dest=tmp_path, needsExecutionTool="false")
    assert fmu.exists()
    res = fmpy.simulate_fmu(str(fmu), stop_time=0.5)

    assert res["realOut"][-1] == pytest.approx(res["time"][-1], rel=1e-7)


@pytest.mark.integration
def test_integration_demo_MX(tmp_path):
    script_file = Path(__file__).parent / "slaves/pythonslaveMX.py"
    fmu = FmuBuilder.build_FMU(script_file, dest=tmp_path, needsExecutionTool="false")
    assert fmu.exists()
    res = fmpy.simulate_fmu(str(fmu), stop_time=0.5)


@pytest.mark.integration
def test_integration_solve_MX(tmp_path):
    script_file = Path(__file__).parent / "slaves/pythonslaveMX.py"
    fmu = FmuBuilder.build_FMU(script_file, dest=tmp_path, needsExecutionTool="false")
    assert fmu.exists()

    md = fmpy.read_model_description(str(fmu))
    unzipdir = fmpy.extract(str(fmu))
    model = fmpy.fmi3.FMU3Model(guid=md.guid,
                                unzipDirectory=unzipdir,
                                modelIdentifier=md.modelExchange.modelIdentifier,
                                instanceName="instance"
                                )
    model.instantiate()
    model.enterInitializationMode()
    model.exitInitializationMode()
    
    # forward euler
    t = 0.0
    step_size = 0.1
    
    values = (ctypes.c_double * 1)(0.0)
    states = (ctypes.c_double *1)(0.0)

    model.getContinuousStateDerivatives(values, 1)
    model.getContinuousStates(states, 1)
    
    assert values[0] == pytest.approx(-1.0, rel=1e-7)

    der = values[0]
    new_state = states[0] + der * step_size

    model.setContinuousStates((ctypes.c_double * 1)(new_state), 1)
    model.setTime(t + step_size)
    
    model.getContinuousStates(states, 1)
    
    assert states[0] == pytest.approx(new_state, rel=1e-7)

@pytest.mark.integration
def test_integration_demo_CS_MX(tmp_path):
    script_file = Path(__file__).parent / "slaves/pythonslaveMXCS.py"
    fmu = FmuBuilder.build_FMU(script_file, dest=tmp_path, needsExecutionTool="false")
    assert fmu.exists()
    res = fmpy.simulate_fmu(str(fmu), stop_time=0.5, fmi_type="ModelExchange")
    
    res1 = fmpy.simulate_fmu(str(fmu), stop_time=0.5, fmi_type="CoSimulation")
    
    assert res[-1][0] == pytest.approx(res1[-1][0], rel=1e-7)
    assert res[-1][1] == pytest.approx(res1[-1][1], rel=0.1)


@pytest.mark.integration
def test_integration_reset(tmp_path):
    script_file = Path(__file__).parent / "slaves/pythonslave.py"
    fmu = FmuBuilder.build_FMU(script_file, dest=tmp_path, needsExecutionTool="false")
    assert fmu.exists()

    md = fmpy.read_model_description(str(fmu))
    unzipdir = fmpy.extract(str(fmu))
    model = fmpy.fmi3.FMU3Slave(guid=md.guid,
                                unzipDirectory=unzipdir,
                                modelIdentifier=md.coSimulation.modelIdentifier,
                                instanceName="instance"
                                )
    model.instantiate()
    model.enterInitializationMode()
    model.exitInitializationMode()

    vars = mapped(md)
    vr = vars["realOut"].valueReference
    dt = 0.1

    initial_value = model.getFloat64([vr])[0]
    assert initial_value == pytest.approx(3.0, rel=1e-7)
    model.doStep(0.0, dt, True)
    read = model.getFloat64([vr])[0]
    assert read == pytest.approx(dt, rel=1e-7)
    model.reset()
    read = model.getFloat64([vr])[0]
    assert read == pytest.approx(initial_value, rel=1e-7)

    model.terminate()
    model.freeInstance()


@pytest.mark.integration
def test_integration_get_state(tmp_path):
    script_file = Path(__file__).parent / "slaves/pythonslave.py"
    fmu = FmuBuilder.build_FMU(
        script_file,
        dest=tmp_path,
        needsExecutionTool="false",
        canGetAndSetFMUstate="true")
    assert fmu.exists()

    md = fmpy.read_model_description(str(fmu))
    unzipdir = fmpy.extract(str(fmu))
    model = fmpy.fmi3.FMU3Slave(guid=md.guid,
                                unzipDirectory=unzipdir,
                                modelIdentifier=md.coSimulation.modelIdentifier,
                                instanceName="instance"
                                )
    model.instantiate()
    model.enterInitializationMode()
    model.exitInitializationMode()

    vars = mapped(md)
    vr = vars["realOut"].valueReference
    dt = 0.1
    t = 0.0

    def step_model():
        nonlocal t
        model.doStep(t, dt, True)
        t += dt

    step_model()
    state = model.getFMUState()
    assert model.getFloat64([vr])[0] == pytest.approx(dt, rel=1e-7)
    step_model()
    assert model.getFloat64([vr])[0] == pytest.approx(dt * 2, rel=1e-7)
    model.setFMUState(state)
    assert model.getFloat64([vr])[0] == pytest.approx(dt, rel=1e-7)
    step_model()
    assert model.getFloat64([vr])[0] == pytest.approx(dt * 3, rel=1e-7)
    model.freeFMUState(state)

    model.terminate()
    model.freeInstance()


@pytest.mark.integration
def test_integration_get_serialize_state(tmp_path):

    script_file = Path(__file__).parent / "slaves/pythonslave.py"
    fmu = FmuBuilder.build_FMU(
        script_file,
        dest=tmp_path,
        canGetAndSetFMUstate="true",
        canSerializeFMUstate="true")
    assert fmu.exists()

    md = fmpy.read_model_description(fmu)
    unzip_dir = fmpy.extract(fmu)

    model = fmpy.fmi3.FMU3Slave(
        guid=md.guid,
        unzipDirectory=unzip_dir,
        modelIdentifier=md.coSimulation.modelIdentifier,
        instanceName='instance1')

    model.instantiate()
    model.enterInitializationMode()
    model.exitInitializationMode()

    vars = mapped(md)
    vrs = [vars["realOut"].valueReference]
    t = 0.0
    dt = 0.1

    def step_model():
        nonlocal t
        model.doStep(t, dt)
        t += dt

    step_model()
    state = model.getFMUState()
    assert model.getFloat64(vrs)[0] == pytest.approx(dt, rel=1e-7)
    step_model()
    assert model.getFloat64(vrs)[0] == pytest.approx(dt * 2, rel=1e-7)
    model.setFMUState(state)
    assert model.getFloat64(vrs)[0] == pytest.approx(dt, rel=1e-7)
    step_model()
    assert model.getFloat64(vrs)[0] == pytest.approx(dt * 3, rel=1e-7)

    serialize_fmu_state = model.serializeFMUState(state)
    model.freeFMUState(state)
    de_serialize_fmu_state = model.deserializeFMUState(serialize_fmu_state)
    model.setFMUState(de_serialize_fmu_state)
    assert model.getFloat64(vrs)[0] == pytest.approx(dt, rel=1e-7)

    model.freeFMUState(de_serialize_fmu_state)

    model.terminate()
    model.freeInstance()


@pytest.mark.integration
def test_integration_get(tmp_path):
    script_file = Path(__file__).parent / "slaves/pythonslave.py"
    fmu = FmuBuilder.build_FMU(script_file, dest=tmp_path, needsExecutionTool="false")
    assert fmu.exists()

    md = fmpy.read_model_description(fmu)
    unzip_dir = fmpy.extract(fmu)

    model = fmpy.fmi3.FMU3Slave(
        guid=md.guid,
        unzipDirectory=unzip_dir,
        modelIdentifier=md.coSimulation.modelIdentifier,
        instanceName='instance1')

    model.instantiate()
    model.enterInitializationMode()
    model.exitInitializationMode()

    to_test = {
        "intParam": 42,
        "intOut": 23,
        "realOut": 3.0,
        "booleanVariable": True,
        "stringVariable": "Hello World!",
        "realIn": 2.0 / 3.0,
        "booleanParameter": False,
        "stringParameter": "dog",
        "container.someReal": 99.0,
        "container.subContainer.someInteger": -15
    }

    model_value = None
    variables = mapped(md)
    for key, value in to_test.items():
        var = variables[key]
        vrs = [var.valueReference]
        if var.type == "Int32":
            model_value = model.getInt32(vrs)[0]
        elif var.type == "Float64":
            model_value = model.getFloat64(vrs)[0]
        elif var.type == "Boolean":
            model_value = model.getBoolean(vrs)[0]
        elif var.type == "String":
            model_value = model.getString(vrs)[0]
        else:
            pytest.xfail("Unsupported type")

        assert model_value == value

    model.terminate()
    model.freeInstance()

@pytest.mark.integration
def test_integration_get_array(tmp_path):
    script_file = Path(__file__).parent / "slaves/pythonslave_arraytypes.py"
    fmu = FmuBuilder.build_FMU(script_file, dest=tmp_path, needsExecutionTool="false")
    assert fmu.exists()

    md = fmpy.read_model_description(fmu)
    unzip_dir = fmpy.extract(fmu)

    model = fmpy.fmi3.FMU3Slave(
        guid=md.guid,
        unzipDirectory=unzip_dir,
        modelIdentifier=md.coSimulation.modelIdentifier,
        instanceName='instance1')

    model.instantiate()
    model.enterInitializationMode()
    model.exitInitializationMode()

    to_test = {
        "int32_output": [1,2,3,4,5,6,7,8,9,10],
        "int64_output": [1,2,3,4,5,6,7,8,9,10],
        "uint64_output": [1,2,3,4,5,6,7,8,9,10],
        "float64_output": [1.0,2.0,3.0,4.0,5.0,6.0,7.0,8.0,9.0,10.0],
        "boolean_output": [False, True, False, True, True, False, False, True, False, True]
    }

    model_value = None
    variables = mapped(md)
    for key, value in to_test.items():
        var = variables[key]
        vrs = [var.valueReference]
        if var.type == "Int32":
            model_values = model.getInt32(vrs, nValues=10)
        elif var.type == "Int64":
            model_values = model.getInt64(vrs, nValues=10)
        elif var.type == "UInt64":
            model_values = model.getUInt64(vrs, nValues=10)
        elif var.type == "Float64":
            model_values = model.getFloat64(vrs, nValues=10)
        elif var.type == "Boolean":
            model_values = model.getBoolean(vrs, nValues=10)
        else:
            pytest.xfail("Unsupported type")

        assert len(model_values) == len(value)
        assert model_values == value
        
    model.terminate()
    model.freeInstance()


@pytest.mark.integration
def test_integration_read_from_file(tmp_path):
    script_file = Path(__file__).parent / "slaves/pythonslave_read_file.py"
    project_file = Path(__file__).parent / "data/hello.txt"
    fmu = FmuBuilder.build_FMU(script_file, project_files=[project_file], dest=tmp_path, needsExecutionTool="false")
    assert fmu.exists()

    md = fmpy.read_model_description(fmu)
    unzip_dir = fmpy.extract(fmu)

    model = fmpy.fmi3.FMU3Slave(
        guid=md.guid,
        unzipDirectory=unzip_dir,
        modelIdentifier=md.coSimulation.modelIdentifier,
        instanceName='instance1')

    model.instantiate()
    model.enterInitializationMode()
    model.exitInitializationMode()

    variables = mapped(md)
    var = variables["file_content"]
    model_value = model.getString([var.valueReference])[0]

    with (open(project_file, 'r')) as file:
        data = file.read()

    assert model_value == data

    model.terminate()
    model.freeInstance()


@pytest.mark.integration
def test_integration_set(tmp_path):
    script_file = Path(__file__).parent / "slaves/pythonslave.py"
    fmu = FmuBuilder.build_FMU(script_file, dest=tmp_path, needsExecutionTool="false")
    assert fmu.exists()

    md = fmpy.read_model_description(fmu)
    unzip_dir = fmpy.extract(fmu)

    model = fmpy.fmi3.FMU3Slave(
        guid=md.guid,
        unzipDirectory=unzip_dir,
        modelIdentifier=md.coSimulation.modelIdentifier,
        instanceName='instance1')

    model.instantiate()
    model.enterInitializationMode()
    model.exitInitializationMode()

    to_test = {
        "intParam": 20,
        "realIn": 1.0 / 3.0,
        "booleanParameter": True,
        "stringParameter": "cat",
        "container.someReal": 42.0,
        "container.subContainer.someInteger": 421
    }

    model_value = None
    variables = mapped(md)
    for key, value in to_test.items():
        var = variables[key]
        vrs = [var.valueReference]
        if var.type == "Int32":
            model.setInt32(vrs, [value])
            model_value = model.getInt32(vrs)[0]
        elif var.type == "Float64":
            model.setFloat64(vrs, [value])
            model_value = model.getFloat64(vrs)[0]
        elif var.type == "Boolean":
            model.setBoolean(vrs, [value])
            model_value = model.getBoolean(vrs)[0]
        elif var.type == "String":
            model.setString(vrs, [value])
            model_value = model.getString(vrs)[0]
        else:
            pytest.xfail("Unsupported type")

        assert model_value == value

    model.terminate()
    model.freeInstance()

@pytest.mark.integration
def test_integration_set_array(tmp_path):
    script_file = Path(__file__).parent / "slaves/pythonslave_arraytypes.py"
    fmu = FmuBuilder.build_FMU(script_file, dest=tmp_path, needsExecutionTool="false")
    assert fmu.exists()

    md = fmpy.read_model_description(fmu)
    unzip_dir = fmpy.extract(fmu)

    model = fmpy.fmi3.FMU3Slave(
        guid=md.guid,
        unzipDirectory=unzip_dir,
        modelIdentifier=md.coSimulation.modelIdentifier,
        instanceName='instance1')

    model.instantiate()
    model.enterInitializationMode()
    model.exitInitializationMode()

    to_test = {
        "int32_input": [1,2,3,4,5,6,7,8,9,10],
        "int64_input": [1,2,3,4,5,6,7,8,9,10],
        "uint64_input": [1,2,3,4,5,6,7,8,9,10],
        "float64_input": [1.0,2.0,3.0,4.0,5.0,6.0,7.0,8.0,9.0,10.0],
        "boolean_input": [False, True, False, True, True, False, False, True, False, True]
    }

    model_value = None
    variables = mapped(md)
    for key, value in to_test.items():
        var = variables[key]
        vrs = [var.valueReference]
        if var.type == "Int32":
            model.setInt32(vrs, value)
            model_value = model.getInt32(vrs, nValues=10)
        elif var.type == "Int64":
            model.setInt64(vrs, value)
            model_value = model.getInt64(vrs, nValues=10)
        elif var.type == "UInt64":
            model.setUInt64(vrs, value)
            model_value = model.getUInt64(vrs, nValues=10)
        elif var.type == "Float64":
            model.setFloat64(vrs, value)
            model_value = model.getFloat64(vrs,nValues=10)
        elif var.type == "Boolean":
            model.setBoolean(vrs, value)
            model_value = model.getBoolean(vrs, nValues=10)
        else:
            pytest.xfail("Unsupported type")
        
        assert list(model_value) == value

    model.terminate()
    model.freeInstance()


@pytest.mark.integration
def test_simple_integration_fmpy(tmp_path):

    script_file = Path(__file__).parent / "slaves/pythonslave.py"
    fmu = FmuBuilder.build_FMU(script_file, dest=tmp_path)
    assert fmu.exists()
    res = fmpy.simulate_fmu(str(fmu), stop_time=2.0)

    assert res["realOut"][-1] == pytest.approx(res["time"][-1], rel=1e-7)


@pytest.mark.integration
def test_integration_has_local_dep(tmp_path):

    script_file = Path(__file__).parent / "slaves/slavewithdep.py"
    local_file = Path(__file__).parent / "slaves/localmodule.py"

    fmu = FmuBuilder.build_FMU(
        script_file,
        dest=tmp_path,
        project_files=[local_file],
        needsExecutionTool="false",
    )
    assert fmu.exists()

    res = fmpy.simulate_fmu(str(fmu), stop_time=0.5)

    assert res["realOut"][-1] == pytest.approx(
        22.0 * 5.0 * math.exp(res["time"][-1] / 0.1), rel=1e-7
    )


@pytest.mark.integration
def test_integration_throw_py_error(tmp_path):

    script_file = Path(__file__).parent / "slaves/PythonSlaveWithException.py"
    fmu = FmuBuilder.build_FMU(script_file, dest=tmp_path)
    assert fmu.exists()

    with pytest.raises(Exception):
        fmpy.simulate_fmu(str(fmu), stop_time=1.0)
