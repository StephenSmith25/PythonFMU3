import pytest
import pathlib
import re
import tempfile

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

@pytest.mark.doc
def test_readme():
    test_dir = pathlib.Path(__file__).parent
    fpath = test_dir.parent.parent / "README.md"
    
    # extract Python code
    code_blocks = extract_python_code_from_md(fpath)

    namespace = {}
    exec("from pythonfmu3 import *", namespace)

    for i, code in enumerate(code_blocks):
        try:
            exec(code, namespace)
            print(f"✅ Code block {i+1} executed successfully")
        except Exception as e:
            pytest.fail(f"Code block {i+1} failed: {e}\nCode:\n{code}")
    



@pytest.mark.doc
def test_cosimulation_examples():
    """Test that all Python examples in usage.md actually work"""
    test_dir = pathlib.Path(__file__).parent
    usage_file = test_dir.parent.parent / "docs" / "usage.md"
    
    # Extract Python code
    code_blocks = extract_python_code_from_md(usage_file)
    
    # Create a test namespace
    namespace = {}
    exec("from pythonfmu3 import *", namespace)
    
    # Execute each code block
    for i, code in enumerate(code_blocks):
        try:
            exec(code, namespace)
            print(f"✅ Code block {i+1} executed successfully")
        except Exception as e:
            pytest.fail(f"Code block {i+1} failed: {e}\nCode:\n{code}")
            
    assert 'LinearTransform' in namespace, "LinearTransform class not found"
    assert 'PIDController' in namespace, "PIDController class not found"

    # Test instantiation
    lt = namespace['LinearTransform'](instance_name="test")
    pc = namespace['PIDController'](instance_name="test")


@pytest.mark.doc
def test_model_exchange_examples():
    """Test Model Exchange examples"""
    test_dir = pathlib.Path(__file__).parent
    mx_file = test_dir.parent.parent / "docs" / "usageMX.md"
    
    code_blocks = extract_python_code_from_md(mx_file)
    
    namespace = {}
    exec("from pythonfmu3 import *", namespace)
    
    for i, code in enumerate(code_blocks):
        try:
            exec(code, namespace)
        except Exception as e:
            pytest.fail(f"MX Code block {i+1} failed: {e}")
    
    # Test that classes were actually created
    assert 'VanDerPol' in namespace, "VanDerPol class not found"
    assert 'BouncingBall' in namespace, "BouncingBall class not found"
    
    # Test instantiation
    vdp = namespace['VanDerPol'](instance_name="test")
    
    bb = namespace['BouncingBall'](instance_name="test")