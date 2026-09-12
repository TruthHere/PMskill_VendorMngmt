#!/usr/bin/env python3
"""One-time migration: package folder names, .skill/, 项目档案/, tracker rename."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from common import (
    BACKGROUND_MD,
    LEGACY_ARCHIVE_DIRS,
    LEGACY_SYSTEM_DIRS,
    MAILBOX_STATE_JSON,
    PENDING_JSON,
    PROJECT_ARCHIVE_DIR,
    PROJECT_JSON,
    SCHEDULE_JSON,
    SYSTEM_DIR,
    TRACKER_CSV_LEGACY,
    TRACKER_SUFFIX,
    load_json,
    load_tracker_packages,
    package_folder_name,
    project_archive_dir,
    resolve_tracker_path,
    save_json,
    save_tracker_packages,
    system_dir,
    system_file,
    tracker_basename,
    write_project_background_md,
)

SYSTEM_FILES = (PROJECT_JSON, PENDING_JSON, SCHEDULE_JSON, MAILBOX_STATE_JSON)
JUNK_FILES = ("tracker.json", "tracker.md", "_TEST_NOTE_mailbox_retarget.txt")
SKIP_DIRS = {SYSTEM_DIR, *LEGACY_SYSTEM_DIRS, PROJECT_ARCHIVE_DIR, *LEGACY_ARCHIVE_DIRS, "inbox", ".git"}


def move_system_files(project_root: Path, *, dry_run: bool) -> list[str]:
    root = project_root.expanduser().resolve()
    sys_dir = root / SYSTEM_DIR
    actions: list[str] = []

    if not sys_dir.exists() and not dry_run:
        sys_dir.mkdir(parents=True, exist_ok=True)

    for legacy_name in LEGACY_SYSTEM_DIRS:
        legacy = root / legacy_name
        if legacy.is_dir() and legacy_name != SYSTEM_DIR:
            actions.append(f"rename {legacy_name}/ → {SYSTEM_DIR}/")
            if not dry_run:
                if sys_dir.exists():
                    for child in legacy.iterdir():
                        dest = sys_dir / child.name
                        if not dest.exists():
                            shutil.move(str(child), str(dest))
                    legacy.rmdir()
                else:
                    legacy.rename(sys_dir)

    for name in SYSTEM_FILES:
        for base in (root, *(root / d for d in LEGACY_SYSTEM_DIRS)):
            src = base / name
            if src.is_file() and base != sys_dir:
                dst = sys_dir / name
                if not dst.exists():
                    actions.append(f"move {src.relative_to(root)} → {SYSTEM_DIR}/{name}")
                    if not dry_run:
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(src), str(dst))

    for inbox_name in ("inbox",):
        for base in (root, *(root / d for d in LEGACY_SYSTEM_DIRS)):
            inbox_src = base / inbox_name
            inbox_dst = sys_dir / inbox_name
            if inbox_src.is_dir() and base != sys_dir and not inbox_dst.exists():
                actions.append(f"move {inbox_src.relative_to(root)}/ → {SYSTEM_DIR}/inbox/")
                if not dry_run:
                    shutil.move(str(inbox_src), str(inbox_dst))

    for junk in JUNK_FILES:
        path = root / junk
        if path.is_file():
            actions.append(f"delete {junk}")
            if not dry_run:
                path.unlink()

    return actions


def rename_project_archive(project_root: Path, *, dry_run: bool) -> list[str]:
    root = project_root.expanduser().resolve()
    actions: list[str] = []
    target = root / PROJECT_ARCHIVE_DIR
    for legacy in LEGACY_ARCHIVE_DIRS:
        src = root / legacy
        if src.is_dir() and legacy != PROJECT_ARCHIVE_DIR:
            actions.append(f"rename {legacy}/ → {PROJECT_ARCHIVE_DIR}/")
            if not dry_run:
                if target.exists():
                    for child in src.iterdir():
                        dest = target / child.name
                        if not dest.exists():
                            shutil.move(str(child), str(dest))
                    src.rmdir()
                else:
                    src.rename(target)
    return actions


def rename_package_folders(project_root: Path, *, dry_run: bool) -> list[str]:
    root = project_root.expanduser().resolve()
    packages = load_tracker_packages(root)
    actions: list[str] = []

    for idx, pkg in enumerate(packages, start=1):
        old_dir = Path(pkg.get("folder_path") or "")
        if not old_dir.is_dir():
            candidate = root / old_dir.name
            if candidate.is_dir():
                old_dir = candidate
            else:
                actions.append(f"skip {pkg.get('package_name')}: folder missing ({old_dir})")
                continue

        new_name = package_folder_name(
            idx,
            pkg.get("package_name", ""),
            pkg.get("supplier_short") or pkg.get("supplier_name", "待确认"),
        )
        new_dir = root / new_name
        if old_dir.resolve() == new_dir.resolve():
            pkg["folder_path"] = str(new_dir)
            pkg["card_path"] = str(new_dir / "履约条件卡片.html")
            continue

        if new_dir.exists():
            actions.append(f"ERROR {old_dir.name} → {new_name}: target exists")
            continue

        actions.append(f"rename {old_dir.name} → {new_name}")
        if not dry_run:
            old_dir.rename(new_dir)
        pkg["folder_path"] = str(new_dir)
        pkg["card_path"] = str(new_dir / "履约条件卡片.html")

    if packages and not dry_run:
        save_tracker_packages(root, packages)

    return actions


def migrate_tracker_filename(project_root: Path, *, dry_run: bool) -> list[str]:
    root = project_root.expanduser().resolve()
    project = load_json(system_file(root, PROJECT_JSON), {}) or {}
    actions: list[str] = []

    if not project.get("project_name"):
        return ["skip tracker rename: no project_name in project.json"]

    new_name = tracker_basename(project)
    new_path = root / new_name
    old_path = resolve_tracker_path(root)

    if old_path and old_path.name == new_name and old_path.exists():
        actions.append(f"tracker already named {new_name}")
    elif old_path and old_path.exists():
        actions.append(f"rename {old_path.name} → {new_name}")
        if not dry_run:
            if new_path.exists() and new_path != old_path:
                new_path.unlink()
            old_path.rename(new_path)
    elif not dry_run:
        save_tracker_packages(root, load_tracker_packages(root))

    if not dry_run:
        packages = load_tracker_packages(root)
        save_tracker_packages(root, packages)
        actions.append(f"write # 最后更新 header → {new_name}")

    return actions


def migrate(project_root: Path, *, dry_run: bool = False) -> dict:
    root = project_root.expanduser().resolve()
    has_tracker = bool(resolve_tracker_path(root)) or (root / TRACKER_CSV_LEGACY).exists()
    if not has_tracker and not system_file_exists(root):
        raise FileNotFoundError(f"No tracker or project.json in {root}")

    return {
        "project_root": str(root),
        "dry_run": dry_run,
        "system": move_system_files(root, dry_run=dry_run),
        "archive": rename_project_archive(root, dry_run=dry_run),
        "packages": rename_package_folders(root, dry_run=dry_run),
        "tracker": migrate_tracker_filename(root, dry_run=dry_run),
        "background": f"write {BACKGROUND_MD}",
        "background_done": not dry_run and bool(write_project_background_md(root)),
    }


def system_file_exists(root: Path) -> bool:
    for base in (root, *(root / d for d in (SYSTEM_DIR, *LEGACY_SYSTEM_DIRS))):
        if (base / PROJECT_JSON).is_file():
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate project folder layout")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = migrate(Path(args.project_root), dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
