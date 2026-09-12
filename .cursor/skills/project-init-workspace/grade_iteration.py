#!/usr/bin/env python3
"""Programmatic grader for project-init iteration workspaces."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _load(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _has_package_dirs(root: Path) -> bool:
    if not root.is_dir():
        return False
    for p in root.iterdir():
        if p.is_dir() and p.name[:1].isdigit() and "_" in p.name:
            return True
    return False


def _tracker_empty(root: Path) -> bool | None:
    csvs = list(root.glob("*_procurement_packages_status_tracker.csv"))
    if not csvs:
        return None
    # Prefer foundation loader (handles BOM / meta rows)
    try:
        from common import load_tracker_packages  # type: ignore

        return len(load_tracker_packages(root)) == 0
    except Exception:
        text = csvs[0].read_text(encoding="utf-8-sig")
        data_rows = [
            ln
            for ln in text.splitlines()
            if ln.strip()
            and not ln.lstrip().startswith("#")
            and not ln.startswith("序号,")
            and not ln.startswith(",,,")
        ]
        return len(data_rows) == 0


def grade_dialog(run_dir: Path, assertions: list[str]) -> list[dict]:
    out = run_dir / "outputs"
    # project root may be HarborLab under outputs
    candidates = [out / "HarborLab", out]
    root = next((c for c in candidates if (c / ".skill" / "project.json").is_file()), None)
    project = _load(root / ".skill" / "project.json") if root else None
    result = _load(out / "result.json") or {}
    summary = (out / "summary.md").read_text(encoding="utf-8") if (out / "summary.md").is_file() else ""
    used_cli = ("init_project" in summary) or ("run_init" in summary)

    checks = {
        "project.json exists with project_code HARBOR": bool(project and project.get("project_code") == "HARBOR"),
        "tracker exists with empty packages": bool(root and _tracker_empty(root) is True),
        "mailbox.address is HarborLab_AI@163.com": bool(
            project and ((project.get("mailbox") or {}).get("address") == "HarborLab_AI@163.com")
        ),
        "项目背景.md exists": bool(root and (root / "项目背景.md").is_file()),
        "no procurement package folders created": bool(root and not _has_package_dirs(root)),
        "used init_project CLI (not hand-written project.json only)": used_cli,
    }
    return [
        {"text": a, "passed": bool(checks.get(a, False)), "evidence": f"root={root}; result_keys={list(result)}"}
        for a in assertions
    ]


def grade_pending(run_dir: Path, assertions: list[str]) -> list[dict]:
    out = run_dir / "outputs"
    handler = _load(out / "handler_result.json") or _load(out / "result.json") or {}
    root = out / "GhostRoot"
    project_exists = (root / ".skill" / "project.json").is_file()
    pending = _load(root / ".skill" / "pending.json") or {}
    items = pending.get("items") or []
    has_pending_init = any(
        (it.get("step") == "project_init") or (it.get("reason") == "project_not_initialized") for it in items
    )
    summary = (out / "summary.md").read_text(encoding="utf-8") if (out / "summary.md").is_file() else ""
    reason = handler.get("reason") or ""
    # complete init would have project_name+code and tracker
    complete = project_exists and _tracker_empty(root) is not None and (root / "项目背景.md").is_file()
    # for pending path, complete init via silent create is a FAIL for "did not create"
    checks = {
        "handler result reason is project_not_initialized": reason == "project_not_initialized",
        "result auto is false": handler.get("auto") is False,
        "pending.json has project_init item": has_pending_init,
        "did not create a complete initialized project via silent init": not complete,
        "note or reply tells PM/Agent to use init_project / 入口 A": (
            ("init_project" in summary) or ("入口 A" in summary) or ("run_init" in summary) or ("对话" in summary)
        ),
    }
    return [
        {"text": a, "passed": bool(checks.get(a, False)), "evidence": f"reason={reason}; auto={handler.get('auto')}; project_exists={project_exists}"}
        for a in assertions
    ]


def grade_confirm(run_dir: Path, assertions: list[str]) -> list[dict]:
    out = run_dir / "outputs"
    handler = _load(out / "handler_result.json") or {}
    root = out / "HarborExisting"
    project = _load(root / ".skill" / "project.json") or {}
    mailbox = ((project.get("mailbox") or {}).get("address") or "")
    checks = {
        "handler result auto is true": handler.get("auto") is True,
        "mailbox.address updated to HarborLab_AI@163.com": mailbox == "HarborLab_AI@163.com",
        "project_code remains HARBOR": project.get("project_code") == "HARBOR",
        "no new procurement package folders": not _has_package_dirs(root),
        "did not wipe or recreate tracker packages": _tracker_empty(root) is True,
    }
    return [
        {"text": a, "passed": bool(checks.get(a, False)), "evidence": f"auto={handler.get('auto')}; mailbox={mailbox}"}
        for a in assertions
    ]


GRADERS = {
    "dialog-create-empty-project": grade_dialog,
    "mail-handler-pending-not-silent-create": grade_pending,
    "mail-handler-confirm-existing-mailbox": grade_confirm,
}


def main() -> int:
    iter_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    skill1 = (
        Path(__file__).resolve().parents[1] / "contract-fulfillment-struct" / "scripts"
    )
    if str(skill1) not in sys.path:
        sys.path.insert(0, str(skill1))
    from _foundation import foundation_scripts  # noqa: E402

    foundation = foundation_scripts(Path(__file__))
    if str(foundation) not in sys.path:
        sys.path.insert(0, str(foundation))
    for eval_dir in sorted(p for p in iter_dir.iterdir() if p.is_dir() and (p / "eval_metadata.json").is_file()):
        meta = json.loads((eval_dir / "eval_metadata.json").read_text(encoding="utf-8"))
        assertions = meta.get("assertions") or []
        grader = GRADERS.get(eval_dir.name)
        if not grader:
            continue
        for cfg in ("with_skill", "old_skill"):
            run = eval_dir / cfg
            if not run.is_dir():
                continue
            # prefer run-1 layout if present
            target = run / "run-1" if (run / "run-1").is_dir() else run
            expectations = grader(target if (target / "outputs").is_dir() else run, assertions)
            passed = sum(1 for e in expectations if e["passed"])
            total = len(expectations)
            grading = {
                "expectations": expectations,
                "summary": {
                    "passed": passed,
                    "failed": total - passed,
                    "total": total,
                    "pass_rate": (passed / total) if total else 0.0,
                },
            }
            out_path = (run / "run-1" if (run / "run-1").is_dir() else run) / "grading.json"
            # write next to outputs parent
            if (run / "outputs").is_dir():
                out_path = run / "grading.json"
            out_path.write_text(json.dumps(grading, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{eval_dir.name}/{cfg}: {passed}/{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
