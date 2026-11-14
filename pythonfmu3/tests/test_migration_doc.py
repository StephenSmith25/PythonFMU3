"""Check that the PythonFMU3 example in docs/migration.md works (source checkout only)."""
import pathlib

import pytest

from pythonfmu3.tests.test_docs import extract_python_code_from_md

GUIDE = pathlib.Path(__file__).parent.parent.parent / "docs" / "migration.md"


@pytest.mark.doc
def test_migration_guide_example():
    if not GUIDE.exists():
        pytest.skip("docs/migration.md is only available in a source checkout")

    namespace = {}
    for code in extract_python_code_from_md(GUIDE):   # the FMI 2.0 blocks are marked `python skip`
        exec(code, namespace)

    model = namespace["Integrator"](instance_name="test")
    description = model.to_xml()
    assert description.get("author") == "Jane Doe"
    assert [v.causality.name for v in model.vars.values()][0] == "independent"

    model.gain, model.u = 2.0, 1.5
    model.enter_initialization_mode()
    model.exit_initialization_mode()
    t = 0.0
    for _ in range(10):
        model.do_step(t, 0.1)
        t += 0.1
    assert model.y == pytest.approx(3.0)
    assert model.steps == 10
    assert model.time == pytest.approx(1.0)
