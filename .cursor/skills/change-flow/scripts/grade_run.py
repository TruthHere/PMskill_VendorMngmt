#!/usr/bin/env python3
"""Grade change-flow eval outputs (strict, per eval type)."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS.parents[1] / "po-flow" / "scripts"))
from _foundation import foundation_scripts  # noqa: E402

sys.path.insert(0, str(foundation_scripts(Path(__file__))))

from common import load_json, resolve_tracker_path  # noqa: E402

EVAL_TYPES = ("cod", "lifecycle", "out_of_order")
PKG_NAME = "Glazing partition"
CHANGE_KEY = "COT003"


def normalize_change_no(text: str) -> str:
    return re.sub(r"[\s\-_/]+", "", (text or "").upper())


def load_change_log(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    reader = csv.DictReader(lines)
    return [{k: (v or "") for k, v in row.items()} for row in reader if row and any(row.values())]


def find_change_log(output_root: Path) -> Path | None:
    cands = sorted(output_root.glob("*_change_log.csv"))
    return cands[0] if cands else None


def find_pkg_dir(output_root: Path) -> Path | None:
    for p in sorted(output_root.glob("01_*")):
        if p.is_dir() and (p / "card-data.json").exists():
            return p
    return None


def find_row(rows: list[dict[str, str]]) -> dict[str, str] | None:
    for row in rows:
        if normalize_change_no(row.get("变更序号") or "") == CHANGE_KEY:
            if (row.get("采购包名称") or "").strip() == PKG_NAME:
                return row
    return None


def load_process_result(output_root: Path) -> dict:
    for name in ("process_result.json", "result.json"):
        path = output_root / name
        if path.is_file():
            return load_json(path, {}) or {}
    return {}


def tracker_fingerprint(path: Path | None) -> str:
    if not path or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8-sig")


def detect_eval_type(output_root: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    marker = output_root / "eval_type.txt"
    if marker.is_file():
        return marker.read_text(encoding="utf-8").strip()
    name = output_root.name.lower()
    for key in EVAL_TYPES:
        if key.replace("_", "-") in name or key in name:
            return key
    raise SystemExit(f"Cannot detect eval type for {output_root}; pass --eval-type")


def grade_run(output_root: Path, eval_type: str) -> dict:
    expectations: list[dict] = []
    passed_count = 0
    output_root = output_root.expanduser().resolve()

    def check(text: str, ok: bool, evidence: str) -> None:
        nonlocal passed_count
        expectations.append({"text": text, "passed": bool(ok), "evidence": evidence})
        if ok:
            passed_count += 1

    clog_path = find_change_log(output_root)
    rows = load_change_log(clog_path) if clog_path else []
    row = find_row(rows)
    pkg_dir = find_pkg_dir(output_root)
    result = load_process_result(output_root)
    tracker = resolve_tracker_path(output_root)
    baseline = (output_root / "tracker_baseline.txt").read_text(encoding="utf-8") if (output_root / "tracker_baseline.txt").is_file() else ""
    tracker_now = tracker_fingerprint(tracker)

    if eval_type == "cod":
        check("change log exists", bool(clog_path and clog_path.is_file()), str(clog_path) if clog_path else "missing")
        check(
            "row status is COD 已发出",
            bool(row) and (row.get("当前状态") or "") == "COD 已发出",
            (row or {}).get("当前状态", "no row"),
        )
        estimate = (row or {}).get("预估金额") or ""
        check(
            "estimate amount is ¥15,000.00",
            "15,000" in estimate.replace(" ", "") and "¥" in estimate,
            estimate or "empty",
        )
        cod_ts = (row or {}).get("COD已发出") or ""
        check(
            "COD已发出 milestone timestamp filled",
            bool(cod_ts.strip()),
            cod_ts or "empty",
        )
        if pkg_dir:
            archives_04 = list((pkg_dir / "04_变更洽商").glob("*_COD_*.eml"))
            archives_07 = list((pkg_dir / "07_往来文件").glob("*_COD_*.eml"))
            check(
                "eml archived under 04 and 07 with COD stage",
                bool(archives_04) and bool(archives_07),
                f"04={len(archives_04)} 07={len(archives_07)}",
            )
        else:
            check("eml archived under 04 and 07 with COD stage", False, "package dir missing")
        check(
            "procurement tracker unchanged",
            bool(baseline) and tracker_now == baseline,
            "changed" if baseline and tracker_now != baseline else ("ok" if baseline else "no baseline"),
        )

    elif eval_type == "lifecycle":
        check(
            "row status is Change PO 下发",
            bool(row) and (row.get("当前状态") or "") == "Change PO 下发",
            (row or {}).get("当前状态", "no row"),
        )
        final_amt = (row or {}).get("最终确认金额") or ""
        check(
            "final amount is ¥16,800.00 not ¥3.00",
            "16,800" in final_amt.replace(" ", "") and "¥3.00" not in final_amt and final_amt != "¥3",
            final_amt or "empty",
        )
        cod_ts = (row or {}).get("COD已发出") or ""
        pmi_ts = (row or {}).get("PMI已发出") or ""
        check(
            "COD已发出 and PMI已发出 timestamps filled",
            bool(cod_ts.strip()) and bool(pmi_ts.strip()),
            f"COD={cod_ts or 'empty'} PMI={pmi_ts or 'empty'}",
        )
        items = []
        if pkg_dir and (pkg_dir / "card-data.json").is_file():
            items = load_json(pkg_dir / "card-data.json", {}).get("change_items") or []
        # Skill 3 must not write confirmed change onto the fulfillment card
        wrote_card = False
        for item in items:
            if normalize_change_no(str(item.get("number") or "")) == CHANGE_KEY:
                amt = str(item.get("confirmed_amount") or "")
                if "16,800" in amt.replace(" ", ""):
                    wrote_card = True
        check(
            "Skill 3 did not write change_items to card",
            not wrote_card,
            "wrote ¥16,800 to card" if wrote_card else "card clean of this change amount",
        )
        if pkg_dir:
            stages = {"COD", "PMI", "TECH", "TC", "QUOTE", "CP", "CHPO"}
            found = set()
            for p in (pkg_dir / "04_变更洽商").glob("*.eml"):
                for s in stages:
                    if f"_{s}_" in p.name:
                        found.add(s)
            check(
                "seven stage archives under 04 without overwrite",
                found == stages,
                f"found={sorted(found)}",
            )
        else:
            check("seven stage archives under 04 without overwrite", False, "package dir missing")
        check(
            "procurement tracker unchanged",
            bool(baseline) and tracker_now == baseline,
            "changed" if baseline and tracker_now != baseline else ("ok" if baseline else "no baseline"),
        )

    elif eval_type == "out_of_order":
        reason = str(result.get("reason") or "")
        check(
            "process result is pending out_of_order",
            result.get("auto") is False and reason == "out_of_order",
            f"auto={result.get('auto')} reason={reason or 'missing'}",
        )
        check(
            "row status remains COD 已发出",
            bool(row) and (row.get("当前状态") or "") == "COD 已发出",
            (row or {}).get("当前状态", "no row"),
        )
        check(
            "procurement tracker unchanged",
            bool(baseline) and tracker_now == baseline,
            "changed" if baseline and tracker_now != baseline else ("ok" if baseline else "no baseline"),
        )

    else:
        raise SystemExit(f"Unknown eval type: {eval_type}")

    total = len(expectations)
    return {
        "eval_type": eval_type,
        "expectations": expectations,
        "summary": {
            "passed": passed_count,
            "total": total,
            "pass_rate": round(passed_count / total, 4) if total else 0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--eval-type", choices=EVAL_TYPES, default=None)
    args = parser.parse_args()
    eval_type = detect_eval_type(args.output_root, args.eval_type)
    result = grade_run(args.output_root, eval_type)
    out = args.output_root / "grading.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
