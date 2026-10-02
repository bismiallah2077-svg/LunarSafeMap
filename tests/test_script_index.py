#!/usr/bin/env python3
"""Guard against a stale script index.

docs/script_index.md is the human-readable map of the repository.  It is only
useful if it stays complete, so this test fails whenever a tracked script,
test or config file is missing from it.

Run with:  python tests/test_script_index.py
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / "docs" / "script_index.md"


def tracked(pattern):
    """Tracked files matching a git pathspec, or None outside a git checkout."""
    try:
        out = subprocess.run(["git", "ls-files", pattern], cwd=REPO,
                             capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print("  (skipped: not a git checkout - {})".format(exc))
        return None
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def main():
    if not INDEX.exists():
        raise SystemExit("missing {}".format(INDEX))
    text = INDEX.read_text(encoding="utf-8")
    missing, checked = [], 0
    for pattern in ("scripts/*", "tests/*", "configs/*"):
        files = tracked(pattern)
        if files is None:
            return 0
        for f in files:
            if f.endswith("__init__.py"):
                continue
            checked += 1
            if Path(f).name not in text:
                missing.append(f)
    print("checked {:,} tracked files against {}".format(checked, INDEX.name))
    if missing:
        print("MISSING from the index:")
        for f in missing:
            print("  - {}".format(f))
        print("")
        print("RESULT: FAILED -> add them to docs/script_index.md")
        return 1
    print("RESULT: ALL FILES INDEXED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
