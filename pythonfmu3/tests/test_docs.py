import pytest
import pathlib
import re
import tempfile

from pythonfmu3 import Fmi3Causality, Fmi3SlaveBase, Fmi3Variability


def check_model(cls):
    """Instantiate a documented model and check it would work as an FMU.

    Every variable must be readable, inputs and non-constant parameters must be
    settable, and the model description must be generated without errors.
    """
    instance = cls(instance_name="doc_test")
    for var in instance.vars.values():
        var.getter()
        settable = var.causality in (Fmi3Causality.input, Fmi3Causality.parameter, Fmi3Causality.structuralParameter)
        if settable and var.variability != Fmi3Variability.constant:
            assert var.setter is not None, f"{cls.__name__}.{var.name}: no setter (is the attribute created before register_variable?)"
    instance.to_xml()
    return instance


def models_in(namespace):
    return [
        obj for obj in namespace.values()
        if isinstance(obj, type) and issubclass(obj, Fmi3SlaveBase) and obj.__module__ == "__main__"
        and obj.__name__ not in ("Fmi3Slave", "Fmi3SlaveBase")
    ]


def run_blocks(md_file):
    namespace = {"__name__": "__main__"}
    exec("from pythonfmu3 import *", namespace)
    for i, code in enumerate(extract_python_code_from_md(md_file)):
        try:
            exec(code, namespace)
        except Exception as e:
            pytest.fail(f"{pathlib.Path(md_file).name}: code block {i+1} failed: {e}\nCode:\n{code}")
    for model in models_in(namespace):
        check_model(model)
    return namespace

def extract_python_code_from_md(md_file):
    """Extract Python code blocks from markdown, excluding skip blocks"""
    content = pathlib.Path(md_file).read_text()
    
    # Find all python code blocks that aren't marked as skip
    python_blocks = []
    
    # Pattern to match python blocks but not python skip
    pattern = r'```python(?!\s+skip)(?:[^\n]*)\n(.*?)\n```'
    matches = re.findall(pattern, content, re.DOTALL)
    
    for match in matches:
        # Skip blocks that are wrapped in skip-test comments
        if '<!-- skip-test -->' not in content.split(match)[0][-100:]:
            python_blocks.append(match)
    
    return python_blocks

ROOT = pathlib.Path(__file__).parent.parent.parent


def _doc(*parts):
    path = ROOT.joinpath(*parts)
    if not path.exists():
        pytest.skip(f"{path.name} is only available in a source checkout")
    return path


@pytest.mark.doc
def test_readme():
    namespace = run_blocks(_doc("README.md"))
    assert "PythonSlave" in namespace and "PythonSlaveMX" in namespace


@pytest.mark.doc
def test_index():
    namespace = run_blocks(_doc("docs", "index.md"))
    assert "MyModel" in namespace


@pytest.mark.doc
def test_cosimulation_examples():
    """Test that all Python examples in usage.md actually work"""
    namespace = run_blocks(_doc("docs", "usage.md"))
    assert "LinearTransform" in namespace, "LinearTransform class not found"
    assert "PIDController" in namespace, "PIDController class not found"


@pytest.mark.doc
def test_model_exchange_examples():
    """Test Model Exchange examples"""
    namespace = run_blocks(_doc("docs", "usageMX.md"))
    assert "VanDerPol" in namespace, "VanDerPol class not found"
    assert "BouncingBall" in namespace, "BouncingBall class not found"


def test_update_discrete_states_result_aliases():
    from pythonfmu3 import Fmi3UpdateDiscreteStatesResult

    result = Fmi3UpdateDiscreteStatesResult()
    result.discreteStateNeedsUpdate = True
    result.nominalsOfContinuousStatesChanged = True
    assert result.discreteStatesNeedUpdate and result.nominalContinuousStatesChanged
