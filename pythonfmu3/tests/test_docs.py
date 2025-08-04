import pathlib
import pytest

from mktestdocs import check_md_file
import inspect


from pythonfmu3 import Fmi3Slave, Fmi3SlaveBase

@pytest.mark.doc
def test_readme(monkeypatch):
    test_dir = pathlib.Path(__file__).parent
    fpath = test_dir.parent.parent / "README.md"
    monkeypatch.chdir(test_dir)

    check_md_file(fpath=fpath, memory=False)
    
@pytest.mark.doc
def test_cosimulation_usage_doc(monkeypatch):
    test_dir = pathlib.Path(__file__).parent
    fpath = test_dir.parent.parent / "docs" / "usage.md"
    monkeypatch.chdir(test_dir)

    check_md_file(fpath=fpath, memory=True)
    
@pytest.mark.doc
def test_modelexchange_usage_doc(monkeypatch):
    test_dir = pathlib.Path(__file__).parent
    fpath = test_dir.parent.parent / "docs" / "usageMX.md"
    monkeypatch.chdir(test_dir)

    check_md_file(fpath=fpath, memory=True)