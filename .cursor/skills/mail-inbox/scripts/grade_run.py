#!/usr/bin/env python3
"""Grade mail-inbox classify outputs against expected intent/route."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _norm_change(text: str) -> str:
    return (text or "").replace("-", "").replace(" ", "").upper()


def grade_result(result: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    expectations: list[dict[str, Any]] = []
    passed_count = 0

    def check(text: str, ok: bool, evidence: str) -> None:
        nonlocal passed_count
        expectations.append({"text": text, "passed": bool(ok), "evidence": evidence})
        if ok:
            passed_count += 1

    intent = result.get("intent")
    route = result.get("route_to")
    hints = result.get("hints") or {}
    enrichment = result.get("enrichment") or {}

    if "intent" in expected:
        want = expected["intent"]
        check(f"intent is {want}", intent == want, f"got {intent!r}")

    if "route_to" in expected:
        want = expected["route_to"]
        check(f"route_to is {want}", route == want, f"got {route!r}")

    if expected.get("change_no"):
        got = _norm_change(str(hints.get("change_no") or ""))
        want = _norm_change(str(expected["change_no"]))
        check(
            f"change_no is {expected['change_no']}",
            got == want,
            f"got {hints.get('change_no')!r}",
        )

    if expected.get("package_name"):
        got = (hints.get("package_name") or "").strip()
        want = str(expected["package_name"]).strip()
        ok = got == want or want.lower() in got.lower() or got.lower() in want.lower()
        check(f"package_name is {want}", ok, f"got {got!r}")

    if "enrichment_payment_terms" in expected:
        want = bool(expected["enrichment_payment_terms"])
        got = bool(enrichment.get("payment_terms"))
        label = "enrichment.payment_terms is true" if want else "enrichment.payment_terms is false"
        check(label, got == want, f"got {got!r}")

    # Soft negatives only when expected clearly excludes them
    if expected.get("intent") == "fulfillment.raise_po":
        check("not change.change_po", intent != "change.change_po", f"got {intent!r}")
    if str(expected.get("intent") or "").startswith("fulfillment."):
        check("not change.*", not str(intent or "").startswith("change."), f"got {intent!r}")
    if expected.get("intent") == "fulfillment.rfp":
        check("not change.cod", intent != "change.cod", f"got {intent!r}")
        check("not payment_claim", not str(intent or "").startswith("payment_claim"), f"got {intent!r}")
    if expected.get("intent") == "unknown":
        check("not payment_claim", not str(intent or "").startswith("payment_claim"), f"got {intent!r}")

    total = len(expectations)
    return {
        "expectations": expectations,
        "summary": {
            "passed": passed_count,
            "total": total,
            "pass_rate": (passed_count / total) if total else 0.0,
        },
    }


def grade_run(output_root: Path) -> dict[str, Any]:
    output_root = output_root.expanduser().resolve()
    result = load_json(output_root / "result.json")
    expected = load_json(output_root / "expected.json")
    grading = grade_result(result, expected)
    (output_root / "grading.json").write_text(
        json.dumps(grading, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return grading


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output_root", type=Path)
    args = ap.parse_args()
    grading = grade_run(args.output_root)
    print(json.dumps(grading, ensure_ascii=False, indent=2))
    summary = grading.get("summary") or {}
    return 0 if summary.get("passed") == summary.get("total") else 1


if __name__ == "__main__":
    raise SystemExit(main())
