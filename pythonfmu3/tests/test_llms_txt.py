"""Checks for docs/llms.txt (the index for AI tools) and the llms-full.txt build hook."""
import importlib.util
import re
from pathlib import Path

import pytest

from pythonfmu3.tests.test_docs import check_model, models_in

ROOT = Path(__file__).resolve().parents[2]
LLMS = ROOT / "docs" / "llms.txt"
DOCS_URL = "https://pythonfmu3.readthedocs.io/en/latest/"

pytestmark = pytest.mark.skipif(not LLMS.exists(), reason="needs a source checkout with docs/")


def nav_pages():
    text = (ROOT / "mkdocs.yml").read_text()
    return re.findall(r"^\s+- [^:]+: (\S+\.md)$", text, re.MULTILINE)


def test_structure():
    text = LLMS.read_text()
    assert text.startswith("# PythonFMU3\n\n> ")
    assert "## Docs" in text and "## Optional" in text


def test_example_is_a_working_model():
    code = re.search(r"```python\n(.*?)```", LLMS.read_text(), re.DOTALL).group(1)
    namespace = {"__name__": "__main__"}
    exec(code, namespace)
    (cls,) = models_in(namespace)
    instance = check_model(cls)
    instance.u = 3.0
    instance.do_step(0.0, 0.1)
    assert instance.y == 6.0


def test_doc_links_point_at_pages():
    pages = set(nav_pages())
    for url in re.findall(r"\((https://pythonfmu3\.readthedocs\.io/[^)]+)\)", LLMS.read_text()):
        path = url[len(DOCS_URL):]
        if path == "llms-full.txt":
            continue
        assert path.endswith("/") and f"{path[:-1]}.md" in pages, url


def test_llms_full_contains_every_page(tmp_path):
    spec = importlib.util.spec_from_file_location("llms_hook", ROOT / "docs_hooks" / "llms.py")
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    nav = [{page: page} for page in nav_pages()]
    text = hook.build_llms_full(ROOT / "docs", nav, DOCS_URL)
    for page in nav_pages():
        url = DOCS_URL if page == "index.md" else f"{DOCS_URL}{page[:-3]}/"
        assert f"<!-- {page}: {url} -->" in text
    assert "class " in text and len(text) > 10000
