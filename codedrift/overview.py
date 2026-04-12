"""Project overview — structural map for vague queries."""

from pathlib import Path
from typing import List

from .db import CodeDriftDB


def _detect_entry_points(project_dir: str, files: List[str]) -> List[str]:
    candidates = ["main.py", "app.py", "server.py", "index.py", "run.py",
                  "manage.py", "main.go", "main.rs", "index.js", "index.ts",
                  "app.js", "app.ts", "server.js", "server.ts"]
    found = []
    for f in files:
        basename = Path(f).name
        if basename in candidates:
            found.append(f)
    return found


def _test_summary(files: List[str], db: CodeDriftDB) -> dict:
    test_files = [f for f in files if "test" in f.lower() or "spec" in f.lower()]
    if not test_files:
        return {}
    test_dirs = list({str(Path(f).parent) for f in test_files})
    (test_fn_count,) = db.execute(
        "SELECT COUNT(*) FROM symbols WHERE (name LIKE 'test_%' OR name LIKE 'Test%') AND kind = 'function'"
    )[0]
    return {
        "files": len(test_files),
        "dirs": test_dirs[:3],
        "functions": test_fn_count,
    }


def overview(db: CodeDriftDB, project_dir: str) -> str:
    stats = db.stats()
    files = db.list_files()
    module_rows = db.module_summary()
    entry_points = _detect_entry_points(project_dir, files)
    test_info = _test_summary(files, db)

    project_name = Path(project_dir).name
    lines = [
        f"Project: {project_name}",
        f"{stats['files']} files, {stats['symbols']} symbols",
        "",
    ]

    # Language breakdown
    if stats["languages"]:
        lang_parts = [f"{lang} ({n})" for lang, n in stats["languages"].items()]
        lines.append("Languages: " + ", ".join(lang_parts))
        lines.append("")

    # Module breakdown
    if module_rows:
        lines.append("Modules:")
        for row in module_rows[:15]:
            module = row["module"] or "."
            lines.append(f"  {module:<30} → {row['file_count']} files, {row['symbol_count']} symbols")
        lines.append("")

    # Entry points
    if entry_points:
        lines.append("Entry points: " + ", ".join(entry_points))
        lines.append("")

    # Test summary
    if test_info:
        lines.append(
            f"Tests: {test_info['files']} files, {test_info['functions']} test functions"
            + (f" in {', '.join(test_info['dirs'])}" if test_info.get('dirs') else "")
        )
        lines.append("")

    return "\n".join(lines).rstrip()
