import pytest

from pythonfmu3 import Fmi3Slave, ModelExchange
from pythonfmu3 import __version__ as VERSION

from .utils import FMI2PY, PY2FMI

# TODO test xml


@pytest.mark.parametrize("model", ["theModelName", None])
def test_Fmi3Slave_constructor(model):

    class Slave(Fmi3Slave):

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            if model is not None:
                self.modelName = model

        def do_step(self, t, dt):
            return True

    if model is None:
        slave = Slave(instance_name="slaveInstance")
        assert slave.modelName == "Slave"
        assert slave.instance_name == "slaveInstance"
    else:
        slave = Slave(instance_name="slaveInstance")
        assert slave.modelName == model
        assert slave.instance_name == "slaveInstance"


def test_Fmi3Slave_generation_tool():
    class Slave(Fmi3Slave):
        def do_step(self, t, dt):
            return True
    
    slave = Slave(instance_name="instance")
    xml = slave.to_xml()

    assert xml.attrib['generationTool'] == f"PythonFMU3 {VERSION}"


@pytest.mark.parametrize("fmi_type", FMI2PY)
@pytest.mark.parametrize("value", [
    False, 
    22, 
    2./3., 
    "hello_world"
])
def test_Fmi3Slave_getters(fmi_type, value):
    
    class Slave(Fmi3Slave):

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.var = value
            self.register_variable(PY2FMI[type(value)]("var"))

        def do_step(self, t, dt):
            return True
    
    py_type = FMI2PY[fmi_type]
    fmi_type_name = fmi_type.__qualname__.lower()

    slave = Slave(instance_name="slaveInstance")
    if type(value) is py_type:
        assert getattr(slave, f"get_{fmi_type_name}")([0]) == [value]
    else:
        with pytest.raises(TypeError):
            getattr(slave, f"get_{fmi_type_name}")([0])


@pytest.mark.parametrize("fmi_type", FMI2PY)
@pytest.mark.parametrize("value", [
    False, 
    22, 
    2./3., 
    "hello_world",
])
def test_Fmi3Slave_setters(fmi_type, value):

    class Slave(Fmi3Slave):

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.var = None
            self.register_variable(PY2FMI[type(value)]("var"))

        def do_step(self, t, dt):
            return True
    
    slave = Slave(instance_name="slaveInstance")
    py_type = FMI2PY[fmi_type]
    fmi_type_name = fmi_type.__qualname__.lower()

    if type(value) is py_type:
        set_method = getattr(slave, f"set_{fmi_type_name}")
        set_method([0], [value])
        assert getattr(slave, f"get_{fmi_type_name}")([0]) == [value]
    else:
        set_method = getattr(slave, f"set_{fmi_type_name}")
        with pytest.raises(TypeError):
            set_method([0], [value])


def test_Fmi3Slave_log_categories():
    class Slave(Fmi3Slave):
        def do_step(self, t, dt):
            return True
    
    slave = Slave(instance_name="instance")
    xml = slave.to_xml()

    categories = xml.find("LogCategories")
    assert len(categories) == len(Slave.log_categories)
    for category, description in Slave.log_categories.items():
        assert categories.find(f"Category[@name='{category}'][@description='{description}']") is not None


@pytest.mark.parametrize("new_categories", [
    dict(),
    {
        "logStatusWarning": "Log messages with fmi3Warning status.",
        "logStatusError": "Log messages with fmi3Error status.",
        "logStatusFatal": "Log messages with fmi3Fatal status.",
        "logAll": "Log all messages."
    },
    {
        "logCustom1": "My first custom log category",
        "logCustom2": "My second custom log category"
    }
])
def test_Fmi3Slave_customized_log_categories(new_categories):
    class Slave(Fmi3Slave):
        log_categories = new_categories

        def do_step(self, t, dt):
            return True
    
    slave = Slave(instance_name="instance")
    xml = slave.to_xml()

    categories = xml.find("LogCategories")

    if len(new_categories) > 0:
        assert len(categories) == len(Slave.log_categories)
        for category, description in Slave.log_categories.items():
            assert categories.find(f"Category[@name='{category}'][@description='{description}']") is not None
    else:
        assert categories is None


def test_Fmi3Slave_model_exchange():
    class Slave(Fmi3Slave, ModelExchange):

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.time = 0.0

        def get_continuous_state_derivatives(self, vals):
            return []
    
    slave = Slave(instance_name="instance")
    xml = slave.to_xml()

    categories = xml.find("ModelExchange")
    
    assert categories is not None, "ModelExchange category should be present in the XML"

