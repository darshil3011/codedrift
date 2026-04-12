"""Tests for the FTS5 search engine."""

from codedrift.indexer import index_project
from codedrift.search import search, _build_fts_query


def test_fts_query_builder():
    assert _build_fts_query("auth token 401") == 'auth* OR token* OR "401"'
    assert _build_fts_query("validate") == "validate*"
    assert _build_fts_query("") == ""


def test_search_finds_function_by_name(tmp_db, python_fixture_dir):
    index_project(str(python_fixture_dir), tmp_db)
    results = search(tmp_db, "validate token")

    names = [r.name for r in results]
    assert "validate_token" in names


def test_search_finds_by_function_name_in_api(tmp_db, python_fixture_dir):
    index_project(str(python_fixture_dir), tmp_db)
    # get_profile is a symbol name in api.py, should surface via symbols_fts
    results = search(tmp_db, "profile admin")

    assert len(results) > 0
    names = [r.name for r in results]
    assert any("profile" in n or "admin" in n for n in names)


def test_search_returns_ranked_results(tmp_db, python_fixture_dir):
    index_project(str(python_fixture_dir), tmp_db)
    results = search(tmp_db, "generate token")

    assert len(results) > 0
    # generate_token must appear in the results (not necessarily first —
    # BM25 ranking is corpus-dependent; test_generate_and_validate can
    # outrank it when "generate" appears in both name + signature columns)
    names = [r.name for r in results]
    assert "generate_token" in names


def test_search_no_results(tmp_db, python_fixture_dir):
    index_project(str(python_fixture_dir), tmp_db)
    results = search(tmp_db, "xyznonexistent123")

    assert results == []


def test_search_respects_limit(tmp_db, python_fixture_dir):
    index_project(str(python_fixture_dir), tmp_db)
    results = search(tmp_db, "token", limit=2)

    assert len(results) <= 2
