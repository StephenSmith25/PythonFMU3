from enum import Enum
from random import randint

import pytest

from xml.etree import ElementTree

from pythonfmu3 import Fmi3Slave
from pythonfmu3.enums import Fmi3Causality, Fmi3Initial, Fmi3Variability
from pythonfmu3.variables import Boolean, Integer, Real, ModelVariable, String

from .utils import PY2FMI

MODEL_VARIABLE_ATTRIBUTES = ["name", "valueReference", "description", "causality", "variability", "initial"]


def test_ModelVariable_reference_set_once_only():
    v = ModelVariable('variable')
    v.value_reference = 22

    with pytest.raises(RuntimeError):
        v.value_reference = 33


@pytest.mark.parametrize("causality", list(Fmi3Causality) + [None])
@pytest.mark.parametrize("initial", list(Fmi3Initial) + [None])
@pytest.mark.parametrize("variability", list(Fmi3Variability) + [None])
@pytest.mark.parametrize("name, description", [
    ("var", None),
    ("var", "description of var"),
])
def test_ModelVariable_constructor(causality, initial, variability, name, description):
    var = ModelVariable(name, causality, description, initial, variability)

    assert var.name == name
    assert var.value_reference is None
    assert var.causality == causality
    assert var.description == description
    assert var.initial == initial
    assert var.variability == variability


@pytest.mark.parametrize("fmi_type,value", [
    (Boolean, False),
    (Integer, 22),
    (Real, 2./3.),
    (String, "hello_world"),
])
def test_ModelVariable_getter(fmi_type, value):

    class Slave(Fmi3Slave):

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.var = [value]
            self.register_variable(PY2FMI[type(value)]("var", getter=lambda: self.var[0]))

        def do_step(self, t, dt):
            return True

    fmi_type_name = fmi_type.__qualname__.lower()

    slave = Slave(instance_name="slaveInstance")
    assert getattr(slave, f"get_{fmi_type_name}")([0]) == [value]


@pytest.mark.parametrize("fmi_type,value", [
    (Boolean, False),
    (Integer, 22),
    (Real, 2./3.),
    (String, "hello_world"),
])
def test_ModelVariable_setter(fmi_type, value):

    class Slave(Fmi3Slave):

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.var = [None]
            self.register_variable(
                PY2FMI[type(value)](
                    "var",
                    getter=lambda: self.var[0],
                    setter=lambda v: self.var.__setitem__(0, v)
                )
            )

        def do_step(self, t, dt):
            return True

    slave = Slave(instance_name="slaveInstance")
    fmi_type_name = fmi_type.__qualname__.lower()

    set_method = getattr(slave, f"set_{fmi_type_name}")
    set_method([0, ], [value, ])
    assert getattr(slave, f"get_{fmi_type_name}")([0]) == [value]


@pytest.mark.parametrize("causality", list(Fmi3Causality) + [None])
@pytest.mark.parametrize("initial", list(Fmi3Initial) + [None])
@pytest.mark.parametrize("variability", list(Fmi3Variability) + [None])
@pytest.mark.parametrize("name, description", [
    ("var", None),
    ("var", "description of var"),
])
def test_ModelVariable_to_xml(causality, initial, variability, name, description):
    var = ModelVariable(name, causality, description, initial, variability)
    valueReference = randint(0, 25000)
    var.value_reference = valueReference

    node = var.to_xml()
    assert node.tag == None
    args = locals()
    for attr in MODEL_VARIABLE_ATTRIBUTES:
        value = args[attr]
        if value is not None:
            if isinstance(value, Enum):
                assert node.attrib[attr] == value.name
            else:
                assert node.attrib[attr] == str(value)


@pytest.mark.parametrize("var_type, value", [
    (Boolean, True),
    (Integer, 23),
    (Real, 15.),
    (String, "hello")])
@pytest.mark.parametrize("causality", list(Fmi3Causality) + [None])
@pytest.mark.parametrize("initial", list(Fmi3Initial) + [None])
@pytest.mark.parametrize("variability", list(Fmi3Variability) + [None])
def test_ModelVariable_start(var_type, value, causality, initial, variability):
    var_obj = var_type("var", causality=causality, description="a variable", initial=initial, variability=variability)

    class PySlave(Fmi3Slave):

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            setattr(self, "var", value)
            self.register_variable(var_obj)

        def do_step(self, current_time: float, step_size: float):
            return True

    slave = PySlave(instance_name="testInstance")

    xml = slave.to_xml()
    var_node = xml.find(f".//{var_obj._type}[@name='var']")

    assert var_node is not None

    if ModelVariable.requires_start(var_obj):
        assert var_obj.start == value
    else:
        assert var_obj.start is None


@pytest.mark.parametrize("name,start", [
    ("boolean_name", None),
    ("boolean_another_name", False),
])
def test_Boolean_constructor(name, start):
    r = Boolean(name, start)

    assert r.start == start


@pytest.mark.parametrize("name,start", [
    ("boolean_name", None),
    ("boolean_another_name", True),
    ("boolean_yet_another", False),
])
def test_Boolean_to_xml(name, start):
    r = Boolean(name, start)
    xml = r.to_xml()
    if start is not None:
        assert xml.attrib['start'] == str(start).lower()


@pytest.mark.parametrize("name,start", [
    ("integer_name", None),
    ("integer_another_name", 42),
])
def test_Integer_constructor(name, start):
    r = Integer(name, start)

    assert r.start == start


@pytest.mark.parametrize("name,start", [
    ("integer_name", None),
    ("integer_another_name", 42),
])
def test_Integer_to_xml(name, start):
    r = Integer(name, start)
    xml = r.to_xml()
    if start is not None:
        assert xml.attrib['start'] == str(start)


@pytest.mark.parametrize("name,start", [
    ("real_name", None),
    ("real_another_name", 22.),
])
def test_Real_constructor(name, start):
    r = Real(name, start)

    assert r.start == start


@pytest.mark.parametrize("name,start", [
    ("real_name", None),
    ("real_another_name", 22.),
])
def test_Real_to_xml(name, start):
    r = Real(name, start)
    xml = r.to_xml()
    if start is not None:
        assert xml.attrib['start'] == f"{start:.16g}"


@pytest.mark.parametrize("name,start", [
    ("string_name", None),
    ("string_another_name", "dummy"),
])
def test_String_constructor(name, start):
    r = String(name, start)

    assert r.start == start


@pytest.mark.parametrize("name,start", [
    ("string_name", None),
    ("string_another_name", "dummy"),
])
def test_String_to_xml(name, start):
    r = String(name, start)
    xml = r.to_xml()
    if start is not None:
        assert xml.attrib['start'] == str(start)
