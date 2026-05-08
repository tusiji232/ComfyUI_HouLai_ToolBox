#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lightweight repository health checks for the open-source package."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OK = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_python_syntax() -> None:
    python_files = [ROOT / "__init__.py", *sorted((ROOT / "py").glob("*.py"))]
    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_required_project_files() -> None:
    required_paths = [
        ROOT / "README.md",
        ROOT / "LICENSE",
        ROOT / "SECURITY.md",
        ROOT / "requirements.txt",
        ROOT / "py",
        ROOT / "js",
        ROOT / "skills",
        ROOT / "docs" / "images",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required_paths if not path.exists()]
    expect(not missing, "Missing required project paths: " + ", ".join(missing))


def test_readme_image_references_exist() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    refs = sorted(set(re.findall(r'docs/images/[^" )]+\.png', readme)))
    expect(refs, "README should include node screenshot references")
    missing = [ref for ref in refs if not (ROOT / ref).exists()]
    expect(not missing, "README references missing images: " + ", ".join(missing))


def test_no_obvious_private_artifacts_tracked() -> None:
    forbidden_suffixes = {".pyc", ".pyo", ".log", ".sqlite", ".db"}
    forbidden_names = {".env", "__pycache__"}
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    tracked_paths = [ROOT / line for line in result.stdout.splitlines() if line.strip()]

    bad_paths = []
    for path in tracked_paths:
        if path.name in forbidden_names or path.suffix.lower() in forbidden_suffixes:
            bad_paths.append(str(path.relative_to(ROOT)))

    expect(not bad_paths, "Private/cache artifacts should not be present: " + ", ".join(bad_paths))


def run_test(name: str, func) -> bool:
    try:
        func()
    except Exception as exc:
        print(f"{FAIL} {name}: {exc}")
        return False

    print(f"{OK} {name}")
    return True


def main() -> int:
    tests = [
        ("Python syntax", test_python_syntax),
        ("Required project files", test_required_project_files),
        ("README image references", test_readme_image_references_exist),
        ("No private/cache artifacts", test_no_obvious_private_artifacts_tracked),
    ]
    results = [run_test(name, func) for name, func in tests]
    print("")
    print(f"Passed: {sum(results)}/{len(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
