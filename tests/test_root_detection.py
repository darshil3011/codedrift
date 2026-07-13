"""Root-detection helpers in cli.py, and skill.py's install/refresh behavior.

These close two real bugs: (1) running a query command from a subdirectory
used to silently create a stray, empty index there instead of finding the
real one; (2) install-skill's idempotency check matched any incidental
mention of "codedrift_search" in CLAUDE.md, so it could silently no-op
while still printing a success message.
"""

import pytest

from codedrift.cli import _find_repo_root, _resolve_existing_root, _resolve_index_root
from codedrift.skill import generate_skill_file


def _make_git_repo(root):
    (root / ".git").mkdir(parents=True)
    return root


def test_find_repo_root_from_nested_subdir(tmp_path, monkeypatch):
    repo = _make_git_repo(tmp_path / "repo")
    nested = repo / "src" / "deep"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert _find_repo_root() == repo


def test_find_repo_root_returns_none_outside_any_repo(tmp_path, monkeypatch):
    # tmp_path (under the OS temp dir) and its ancestors have no .git, so
    # walking upward should find nothing.
    lonely = tmp_path / "lonely"
    lonely.mkdir()
    monkeypatch.chdir(lonely)
    assert _find_repo_root() is None


def test_resolve_index_root_explicit_path_wins(tmp_path):
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    assert _resolve_index_root(str(explicit)) == explicit.resolve()


def test_resolve_index_root_reuses_existing_index_over_git_root(tmp_path, monkeypatch):
    repo = _make_git_repo(tmp_path / "repo")
    nested = repo / "sub"
    nested.mkdir()
    (nested / ".codecodedrift").mkdir()
    (nested / ".codecodedrift" / "index.db").write_bytes(b"")
    monkeypatch.chdir(nested)
    # An index already exists right here — must win over walking up to the git root.
    assert _resolve_index_root(None) == nested


def test_resolve_index_root_falls_back_to_git_root(tmp_path, monkeypatch):
    repo = _make_git_repo(tmp_path / "repo")
    nested = repo / "src" / "deep"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    # No existing index anywhere — should default to the git repo root, not cwd.
    assert _resolve_index_root(None) == repo


def test_resolve_index_root_falls_back_to_cwd_outside_git(tmp_path, monkeypatch):
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.chdir(plain)
    assert _resolve_index_root(None) == plain.resolve()


def test_resolve_existing_root_finds_index_from_subdir(tmp_path, monkeypatch):
    project = tmp_path / "project"
    (project / ".codecodedrift").mkdir(parents=True)
    (project / ".codecodedrift" / "index.db").write_bytes(b"")
    nested = project / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert _resolve_existing_root(None) == project


def test_resolve_existing_root_exits_when_nothing_found(tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    with pytest.raises(SystemExit):
        _resolve_existing_root(None)


def test_skill_file_create_then_unchanged_then_update(tmp_path):
    out, status = generate_skill_file(str(tmp_path))
    assert status == "created"
    text_first = out.read_text()

    out, status = generate_skill_file(str(tmp_path))
    assert status == "unchanged"
    assert out.read_text() == text_first


def test_skill_file_ignores_incidental_mention_of_tool_name(tmp_path):
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Notes\nSomeone mentioned codedrift_search here in passing.\n")

    out, status = generate_skill_file(str(tmp_path))

    assert status == "created"
    text = out.read_text()
    assert "Someone mentioned codedrift_search here in passing." in text
    assert "codedrift_memory" in text


def test_skill_file_replaces_stale_block_in_place(tmp_path):
    from codedrift.skill import _END, _START

    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(f"# Notes\n\n{_START}\nstale content\n{_END}\n\n# More notes\n")

    out, status = generate_skill_file(str(tmp_path))

    assert status == "updated"
    text = out.read_text()
    assert "stale content" not in text
    assert "codedrift_memory" in text
    assert "# More notes" in text
