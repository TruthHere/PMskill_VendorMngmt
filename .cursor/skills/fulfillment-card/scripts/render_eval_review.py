#!/usr/bin/env python3
"""Render a simple HTML review page for fulfillment-card eval workspace."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def li(exp: dict) -> str:
    cls = "pass" if exp.get("passed") else "fail"
    mark = "✓" if exp.get("passed") else "✗"
    tier = exp.get("tier") or ""
    tier_html = f' <span class="tier">{tier}</span>' if tier else ""
    return (
        f'<li class="{cls}"><strong>{mark}</strong> {exp.get("text", "")}{tier_html}'
        f'<span class="evidence">{exp.get("evidence", "")}</span></li>'
    )


def config_block(title: str, grading: dict) -> str:
    exps = grading.get("expectations") or []
    fmt = grading.get("format") or {}
    qual = grading.get("quality") or {}
    rate = grading.get("pass_rate")
    pct = f"{rate * 100:.0f}%" if isinstance(rate, (int, float)) else "?"
    return (
        f'<div class="config"><h4>{title}</h4>'
        f'<p>通过率：{pct} ({grading.get("passed")}/{grading.get("total")})'
        f' · format {fmt.get("passed")}/{fmt.get("total")}'
        f' · quality {qual.get("passed")}/{qual.get("total")}</p>'
        f'<ul>{"".join(li(e) for e in exps)}</ul></div>'
    )


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: render_eval_review.py WORKSPACE OUT.html")
    workspace = Path(sys.argv[1]).expanduser().resolve()
    out = Path(sys.argv[2]).expanduser().resolve()
    bench = load(workspace / "benchmark.json") if (workspace / "benchmark.json").is_file() else {}
    std = bench.get("standard_evals") or {}
    diag = bench.get("diagnostic_evals") or {}

    sections = []
    for meta_path in sorted(workspace.glob("eval-*/eval_metadata.json")):
        meta = load(meta_path)
        eval_dir = meta_path.parent
        with_g = load(eval_dir / "with_skill" / "outputs" / "grading.json")
        without_g = load(eval_dir / "without_skill" / "outputs" / "grading.json")
        kind = meta.get("eval_kind") or "standard"
        badge = "诊断" if kind == "diagnostic" else "达标"
        sections.append(
            f'<section><h2>{meta.get("eval_name")} <span class="badge">{badge}</span></h2>'
            f'<pre class="prompt">{meta.get("prompt") or ""}</pre>'
            f'{config_block("with_skill", with_g)}'
            f'{config_block("without_skill", without_g)}'
            f"</section>"
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>fulfillment-card · Eval Review</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 980px; color: #0f172a; }}
h1 {{ margin-bottom: 0.2rem; }}
.summary {{ background: #f1f5f9; padding: 1rem 1.2rem; border-radius: 8px; margin: 1rem 0 2rem; }}
section {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 1.5rem; }}
.prompt {{ background: #f8fafc; padding: 0.8rem; white-space: pre-wrap; font-size: 0.9rem; }}
.config {{ margin-top: 1rem; }}
.pass {{ color: #15803d; }} .fail {{ color: #b91c1c; }}
.evidence {{ display: block; font-size: 0.85rem; color: #64748b; margin-left: 1.2rem; }}
.tier {{ font-size: 0.75rem; color: #64748b; border: 1px solid #cbd5e1; border-radius: 4px; padding: 0 4px; }}
.badge {{ font-size: 0.75rem; background: #e2e8f0; border-radius: 4px; padding: 2px 6px; }}
</style>
</head>
<body>
<h1>fulfillment-card</h1>
<p>Eval workspace：<code>{workspace}</code></p>
<div class="summary">
  <strong>达标题（0–4）</strong><br/>
  with_skill：{std.get("with_skill_pass_rate")}<br/>
  without_skill：{std.get("without_skill_pass_rate")}<br/>
  format / quality（with）：{std.get("with_skill_format_pass_rate")} / {std.get("with_skill_quality_pass_rate")}<br/><br/>
  <strong>诊断题 quality-gap</strong><br/>
  format / quality（with）：{diag.get("with_skill_format_pass_rate")} / {diag.get("with_skill_quality_pass_rate")}
  <span style="color:#64748b">（期望仍出卡 + 提醒到位）</span>
</div>
{"".join(sections)}
<p style="color:#64748b;font-size:0.9rem">规则：<code>.cursor/skills/fulfillment-card/evals/GRADING_RULES.md</code></p>
</body>
</html>
"""
    out.write_text(html, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
