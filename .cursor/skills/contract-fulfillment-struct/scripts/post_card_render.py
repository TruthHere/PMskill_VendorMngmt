#!/usr/bin/env python3
"""Deprecated Skill 1 shim.

请款申请.html 由 fulfillment-card 渲卡片后自动经 payment-form 产出。
本脚本保留仅为兼容旧命令；新流程勿再单独调用。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_FC_SCRIPTS = Path(__file__).resolve().parents[1].parent / "fulfillment-card" / "scripts"
if str(_FC_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_FC_SCRIPTS))
from render_card import patch_and_render  # noqa: E402


def after_card_render(package_dir: Path, render_result: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    If caller already rendered via fulfillment-card, pass through.
    If called alone (legacy), re-render with empty patch so claim form is refreshed.
    """
    package_dir = package_dir.expanduser().resolve()
    out: dict[str, Any] = dict(render_result or {})
    if out.get("claim_form_path") and out.get("card_path"):
        did = list(out.get("did") or [])
        if "fulfillment-card.render" not in did:
            did.append("fulfillment-card.render")
        if "payment-form.sync" not in did:
            did.append("payment-form.sync")
        out["did"] = did
        out["needs_claim_sync"] = False
        out["next_agent"] = [
            "confirm pending only; claim form already produced by payment-form via fulfillment-card"
        ]
        return out

    # Legacy: post_card_render called without a prior render result
    rendered = patch_and_render(package_dir, {})
    rendered["next_agent"] = [
        "confirm pending only; do not re-run sync_claim_form if claim_form_path set"
    ]
    return rendered


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Deprecated: use fulfillment-card/render_card.py (chains payment-form for 请款申请.html)"
    )
    parser.add_argument("--package-dir", required=True)
    args = parser.parse_args()
    result = after_card_render(Path(args.package_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
