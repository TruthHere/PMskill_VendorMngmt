#!/usr/bin/env python3
"""Generate a static HTML review page from skill-creator workspace (Python 3.9+)."""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def render_expectations(items: list) -> str:
    rows = []
    for item in items:
        ok = item.get("passed")
        mark = "✓" if ok else "✗"
        cls = "pass" if ok else "fail"
        rows.append(
            f'<li class="{cls}"><strong>{mark}</strong> '
            f'{html.escape(item.get("text", ""))}'
            f'<span class="evidence">{html.escape(item.get("evidence", ""))}</span></li>'
        )
    return "\n".join(rows)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: render_eval_review.py <workspace> [output.html]")
        sys.exit(1)

    workspace = Path(sys.argv[1]).resolve()
    out_path = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else workspace / "review.html"
    benchmark = load_json(workspace / "benchmark.json")
    summary = benchmark.get("run_summary", {})

    sections = []
    for eval_dir in sorted(workspace.glob("eval-*")):
        meta = load_json(eval_dir / "eval_metadata.json")
        name = meta.get("eval_name", eval_dir.name)
        prompt = meta.get("prompt", "")
        blocks = []
        for config in ("with_skill", "without_skill"):
            grading = load_json(eval_dir / config / "run-1" / "grading.json")
            if not grading:
                grading = load_json(eval_dir / config / "outputs" / "grading.json")
            s = grading.get("summary", {})
            rate = s.get("pass_rate", 0)
            blocks.append(
                f'<div class="config"><h4>{html.escape(config)}</h4>'
                f'<p>通过率：{rate * 100:.0f}% ({s.get("passed", 0)}/{s.get("total", 0)})</p>'
                f'<ul>{render_expectations(grading.get("expectations", []))}</ul></div>'
            )
        sections.append(
            f'<section><h2>{html.escape(name)}</h2>'
            f'<pre class="prompt">{html.escape(prompt)}</pre>'
            f'{"".join(blocks)}</section>'
        )

    ws = summary.get("with_skill", {}).get("pass_rate", {})
    wo = summary.get("without_skill", {}).get("pass_rate", {})
    delta = summary.get("delta", {}).get("pass_rate", "—")

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>contract-fulfillment-struct · Eval Review</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 960px; color: #0f172a; }}
h1 {{ margin-bottom: 0.2rem; }}
.summary {{ background: #f1f5f9; padding: 1rem 1.2rem; border-radius: 8px; margin: 1rem 0 2rem; }}
section {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 1.5rem; }}
.prompt {{ background: #f8fafc; padding: 0.8rem; white-space: pre-wrap; font-size: 0.9rem; }}
.config {{ margin-top: 1rem; }}
.pass {{ color: #15803d; }} .fail {{ color: #b91c1c; }}
.evidence {{ display: block; font-size: 0.85rem; color: #64748b; margin-left: 1.2rem; }}
</style>
</head>
<body>
<h1>contract-fulfillment-struct</h1>
<p>Eval workspace：<code>{html.escape(str(workspace))}</code></p>
<div class="summary">
  <strong>Benchmark</strong><br/>
  with_skill：{ws.get("mean", 0) * 100:.0f}% ± {ws.get("stddev", 0) * 100:.0f}%<br/>
  without_skill：{wo.get("mean", 0) * 100:.0f}% ± {wo.get("stddev", 0) * 100:.0f}%<br/>
  delta：{html.escape(str(delta))}
</div>
{"".join(sections)}
</body>
</html>
"""
    out_path.write_text(page, encoding="utf-8")
    print("Review HTML:", out_path)


if __name__ == "__main__":
    main()
