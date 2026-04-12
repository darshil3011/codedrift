"""Tests for the symbol resolver."""

from codedrift.indexer import index_project
from codedrift.resolver import resolve


def test_resolve_exact_match(tmp_db, python_fixture_dir):
    index_project(str(python_fixture_dir), tmp_db)
    result = resolve(tmp_db, "validate_token", str(python_fixture_dir))

    assert result.name == "validate_token"
    assert result.kind in ("function", "method")
    assert "auth" in result.file
    assert result.source_code != ""
    assert result.start_line > 0


def test_resolve_includes_source_code(tmp_db, python_fixture_dir):
    index_project(str(python_fixture_dir), tmp_db)
    result = resolve(tmp_db, "generate_token", str(python_fixture_dir))

    assert "def generate_token" in result.source_code


def test_resolve_includes_callers(tmp_db, python_fixture_dir):
    index_project(str(python_fixture_dir), tmp_db)
    result = resolve(tmp_db, "validate_token", str(python_fixture_dir))

    # validate_token is called in api.py
    caller_files = [c.file for c in result.callers]
    assert any("api" in f for f in caller_files)


def test_resolve_includes_tests(tmp_db, python_fixture_dir):
    index_project(str(python_fixture_dir), tmp_db)
    result = resolve(tmp_db, "validate_token", str(python_fixture_dir))

    # validate_token is called from test_jwt.py
    test_files = [t.file for t in result.tests]
    assert any("test" in f for f in test_files)


def test_resolve_unknown_symbol(tmp_db, python_fixture_dir):
    index_project(str(python_fixture_dir), tmp_db)
    result = resolve(tmp_db, "this_does_not_exist_xyz", str(python_fixture_dir))

    assert result.kind == "unknown"
    assert result.source_code == ""


def test_resolve_case_insensitive_fallback(tmp_db, python_fixture_dir):
    index_project(str(python_fixture_dir), tmp_db)
    result = resolve(tmp_db, "Validate_Token", str(python_fixture_dir))

    # Should fall back to case-insensitive LIKE and find validate_token
    assert result.name == "validate_token"
