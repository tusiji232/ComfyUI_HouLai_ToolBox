#!/usr/bin/env python3
"""Sync shared style-only skill assets from Detail Skill Manager to HouLai ToolBox."""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def main() -> int:
    toolbox_root = Path(__file__).resolve().parents[1]

    parser = argparse.ArgumentParser(description="Sync style-only skill assets from Skill Manager to HouLai ToolBox")
    parser.add_argument(
        "--manager-root",
        default="",
        help="Path to skill manager project root",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned changes without copying files",
    )
    args = parser.parse_args()

    if not args.manager_root:
        print("[sync] please pass --manager-root PATH")
        return 2

    manager_root = Path(args.manager_root)
    if not manager_root.exists():
        print(f"[sync] manager root not found: {manager_root}")
        return 2

    mappings = [
        (
            first_existing(
                manager_root / "detail_page_extractor_v2.yaml",
                manager_root / "详情页风格骨架提取器.yaml",
            ),
            toolbox_root / "detail_page_extractor_v2.yaml",
        ),
        (
            first_existing(
                manager_root / "法式轻奢视觉风格骨架模板.yaml",
                manager_root / "detail_page_french_skirt.yaml",
            ),
            toolbox_root / "skills" / "法式轻奢视觉风格骨架模板.yaml",
        ),
    ]

    copied = 0
    skipped = 0

    for src, dst in mappings:
        if not src.exists():
            print(f"[sync] missing source: {src}")
            skipped += 1
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        changed = True
        if dst.exists():
            changed = sha1(src) != sha1(dst)

        if not changed:
            print(f"[sync] unchanged: {dst}")
            skipped += 1
            continue

        print(f"[sync] update: {src} -> {dst}")
        if not args.dry_run:
            shutil.copy2(src, dst)
        copied += 1

    print(f"[sync] done. copied={copied}, skipped={skipped}, dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
