"""Tests for the indexer module."""

from codedrift.indexer import index_project


def test_index_python_project(tmp_db, python_fixture_dir):
    stats = index_project(str(python_fixture_dir), tmp_db)

    assert stats["files_indexed"] >= 2   # api.py + auth/jwt.py at minimum
    assert stats["symbols"] >= 5         # generate_token, validate_token, etc.
    assert stats["elapsed"] < 10.0


def test_index_is_incremental(tmp_db, python_fixture_dir):
    # Full index
    s1 = index_project(str(python_fixture_dir), tmp_db, incremental=False)
    # Incremental — nothing changed, so files_indexed should be 0
    s2 = index_project(str(python_fixture_dir), tmp_db, incremental=True)

    assert s2["files_indexed"] == 0
    assert s2["files_skipped"] == s1["files_indexed"]


def test_index_go_project(tmp_db, go_fixture_dir):
    stats = index_project(str(go_fixture_dir), tmp_db)

    assert stats["files_indexed"] >= 1
    assert stats["symbols"] >= 2   # NewServer, Start, main


def test_index_js_project(tmp_db, js_fixture_dir):
    stats = index_project(str(js_fixture_dir), tmp_db)

    assert stats["files_indexed"] >= 1
    assert stats["symbols"] >= 2   # generateToken, validateToken


def test_db_stats_after_index(tmp_db, python_fixture_dir):
    index_project(str(python_fixture_dir), tmp_db)
    stats = tmp_db.stats()

    assert stats["files"] >= 2
    assert stats["symbols"] >= 5
    assert "python" in stats["languages"]
