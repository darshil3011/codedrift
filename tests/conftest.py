"""Shared pytest fixtures for CodeDrift tests."""

import tempfile
from pathlib import Path

import pytest

from codedrift.db import CodeDriftDB


@pytest.fixture
def tmp_db(tmp_path):
    """A fresh in-memory-equivalent CodeDriftDB in a temp directory."""
    db_path = tmp_path / ".codecodedrift" / "index.db"
    db = CodeDriftDB(db_path).connect()
    yield db
    db.close()


@pytest.fixture
def python_fixture_dir():
    return Path(__file__).parent / "fixtures" / "python_project"


@pytest.fixture
def js_fixture_dir():
    return Path(__file__).parent / "fixtures" / "js_project"


@pytest.fixture
def go_fixture_dir():
    return Path(__file__).parent / "fixtures" / "go_project"
