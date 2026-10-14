#!/usr/bin/env python3
"""Render pending.json (+ Tracker summary) as a browser-friendly HTML report."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from common import (  # noqa: E402
    PENDING_JSON,
    PROJECT_JSON,
    load_json,
    load_tracker_packages,
    now_iso,
    system_file,
)
from pending_store import skill_label  # noqa: E402

REASON_LABELS = {
    "tax_rate_uncertain": "税率/含税金额不确定",
    "low_confidence": "字段置信度不足",
    "package_not_found": "找不到采购包",
    "unknown_step": "无法识别邮件步骤",
    "low_confidence_stage0": "项目初始化信息不完整",
    "contract_payment_needs_review": "合同付款节点待确认",
    "change_po_deferred": "Change PO · 待 change-flow",
}

STEP_LABELS = {
    "stage0": "项目初始化",
    "step1": "RFP / RFQ",
    "step2": "技术确认",
    "step3": "Raise PO",
    "step4_payment": "付款条件",
    "step4_contract": "合同",
    "change_po": "Change PO",
    "unknown": "未知",
}


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def render_pending_html(project_root: Path) -> str:
    project_root = project_root.expanduser().resolve()
    project = load_json(system_file(project_root, PROJECT_JSON), {}) or {}
    pending = load_json(system_file(project_root, PENDING_JSON), {"items": []}) or {}
    items = pending.get("items") or []
    open_items = [i for i in items if (i.get("status") or "open") == "open"]
    closed = [i for i in items if (i.get("status") or "") != "open"]
    packages = load_tracker_packages(project_root)

    reason_counts: dict[str, int] = {}
    for item in open_items:
        reason = str(item.get("reason") or "other")
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    cards = []
    for item in open_items:
        fields = item.get("fields") or {}
        reason = str(item.get("reason") or "")
        reason_cn = REASON_LABELS.get(reason, reason or "未标注")
        step = str(item.get("step") or "")
        step_cn = STEP_LABELS.get(step, step)
        owner = skill_label(item.get("skill"))
        subject = " ".join(str(item.get("subject") or "").split())
        note = item.get("note") or ""
        pkg = fields.get("package_name") or "—"
        supplier = fields.get("supplier_name") or "—"
        amount = (
            fields.get("total_amount")
            or fields.get("amount_excl_tax")
            or fields.get("amount_incl_tax")
            or "—"
        )
        badge_class = "badge-tax" if "tax" in reason else "badge-low"
        cards.append(
            f"""
            <article class="card">
              <header>
                <span class="badge {badge_class}">{esc(reason_cn)}</span>
                <span class="meta">{esc(owner)} · {esc(step_cn)} · {esc(item.get('pending_id'))}</span>
              </header>
              <h2>{esc(subject) or '（无主题）'}</h2>
              <dl>
                <div><dt>采购包</dt><dd>{esc(pkg)}</dd></div>
                <div><dt>供应商</dt><dd>{esc(supplier)}</dd></div>
                <div><dt>金额</dt><dd>{esc(amount)}</dd></div>
                <div><dt>创建时间</dt><dd>{esc(item.get('created_at'))}</dd></div>
              </dl>
              {f'<p class="note">{esc(note)}</p>' if note else ''}
              <p class="path">eml: {esc(item.get('eml_path'))}</p>
            </article>
            """
        )

    if not cards:
        cards_html = '<p class="empty">当前没有开放的 pending 项。</p>'
    else:
        cards_html = "\n".join(cards)

    pkg_rows = []
    for pkg in packages:
        pkg_rows.append(
            "<tr>"
            f"<td>{esc(pkg.get('package_name'))}</td>"
            f"<td>{esc(pkg.get('supplier_name'))}</td>"
            f"<td>{esc(pkg.get('package_type'))}</td>"
            f"<td class='center'>{'✓' if (pkg.get('ts_rfp_issued') or '').strip() else '—'}</td>"
            f"<td class='center'>{'✓' if (pkg.get('ts_po_issued') or '').strip() else '—'}</td>"
            f"<td class='num'>{esc(pkg.get('amount_excl_tax') or pkg.get('amount_incl_tax') or '—')}</td>"
            "</tr>"
        )
    pkg_table = (
        "\n".join(pkg_rows)
        if pkg_rows
        else '<tr><td colspan="6" class="empty">暂无采购包</td></tr>'
    )

    chips = "".join(
        f'<span class="chip">{esc(REASON_LABELS.get(k, k))} <b>{v}</b></span>'
        for k, v in sorted(reason_counts.items(), key=lambda x: -x[1])
    ) or '<span class="chip">无开放项</span>'

    name = project.get("project_name") or project_root.name
    code = project.get("project_code") or "—"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Pending 看板 · {esc(name)}</title>
  <style>
    :root {{
      --bg: #f3f1eb;
      --ink: #1c1a16;
      --muted: #6b655c;
      --card: #fffcf7;
      --line: #ddd6c8;
      --accent: #0f5c4c;
      --warn: #8a4b12;
      --warn-bg: #fff1df;
      --tax: #7a2e2e;
      --tax-bg: #fdeceb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", Palatino, "Songti SC", serif;
      color: var(--ink);
      background:
        radial-gradient(1200px 500px at 10% -10%, #e7efe9 0%, transparent 55%),
        radial-gradient(900px 400px at 100% 0%, #f0e6d8 0%, transparent 50%),
        var(--bg);
      line-height: 1.45;
    }}
    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 36px 20px 64px; }}
    header.hero {{
      display: grid;
      gap: 10px;
      margin-bottom: 28px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 20px;
    }}
    .eyebrow {{
      font-family: ui-sans-serif, system-ui, sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font-size: 12px;
      color: var(--accent);
      font-weight: 700;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(28px, 4vw, 40px);
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    .sub {{ color: var(--muted); font-size: 15px; }}
    .stats {{
      display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px;
      font-family: ui-sans-serif, system-ui, sans-serif;
    }}
    .chip {{
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 12px;
      font-size: 13px;
      color: var(--muted);
    }}
    .chip b {{ color: var(--ink); margin-left: 4px; }}
    h2.section {{
      margin: 28px 0 14px;
      font-size: 20px;
    }}
    .grid {{
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px 16px 12px;
      box-shadow: 0 10px 30px rgba(40, 30, 10, 0.04);
    }}
    .card header {{
      display: flex; justify-content: space-between; gap: 8px; align-items: center;
      margin-bottom: 8px;
      font-family: ui-sans-serif, system-ui, sans-serif;
    }}
    .badge {{
      font-size: 12px; font-weight: 700; padding: 4px 8px; border-radius: 999px;
    }}
    .badge-low {{ background: var(--warn-bg); color: var(--warn); }}
    .badge-tax {{ background: var(--tax-bg); color: var(--tax); }}
    .meta {{ color: var(--muted); font-size: 12px; }}
    .card h2 {{
      margin: 0 0 12px;
      font-size: 16px;
      font-family: ui-sans-serif, system-ui, sans-serif;
      font-weight: 650;
      line-height: 1.35;
    }}
    dl {{
      display: grid; gap: 8px; margin: 0;
      font-family: ui-sans-serif, system-ui, sans-serif; font-size: 13px;
    }}
    dl > div {{ display: grid; grid-template-columns: 72px 1fr; gap: 8px; }}
    dt {{ color: var(--muted); }}
    dd {{ margin: 0; word-break: break-word; }}
    .note {{
      margin: 12px 0 0;
      padding: 10px 12px;
      background: #f7f3ea;
      border-radius: 10px;
      font-size: 13px;
      color: #4a4338;
      font-family: ui-sans-serif, system-ui, sans-serif;
    }}
    .path {{
      margin: 10px 0 0;
      font-size: 11px;
      color: #9a9286;
      word-break: break-all;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      overflow: hidden;
      font-family: ui-sans-serif, system-ui, sans-serif;
      font-size: 13px;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: #efe9dd; font-size: 12px; color: var(--muted); font-weight: 700; }}
    tr:last-child td {{ border-bottom: 0; }}
    .center {{ text-align: center; }}
    .num {{ font-variant-numeric: tabular-nums; }}
    .empty {{ color: var(--muted); text-align: center; padding: 24px; }}
    footer {{
      margin-top: 28px;
      color: var(--muted);
      font-size: 12px;
      font-family: ui-sans-serif, system-ui, sans-serif;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <div class="eyebrow">Pending 看板</div>
      <h1>{esc(name)} <span style="color:var(--muted);font-weight:500">· {esc(code)}</span></h1>
      <div class="sub">自动生成于 {esc(now_iso())} · 源文件 `.skill/pending.json`</div>
      <div class="stats">
        <span class="chip">开放 <b>{len(open_items)}</b></span>
        <span class="chip">已关闭 <b>{len(closed)}</b></span>
        <span class="chip">Tracker 包 <b>{len(packages)}</b></span>
        {chips}
      </div>
    </header>

    <h2 class="section">待确认事项</h2>
    <div class="grid">
      {cards_html}
    </div>

    <h2 class="section">Tracker 采购包摘要</h2>
    <table>
      <thead>
        <tr>
          <th>采购包</th><th>供应商</th><th>类型</th><th>RFP</th><th>PO</th><th>金额</th>
        </tr>
      </thead>
      <tbody>
        {pkg_table}
      </tbody>
    </table>

    <footer>
      重新生成：
      <code>python3 scripts/render_pending_report.py --project-root "{esc(project_root)}"</code>
    </footer>
  </div>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Render pending board HTML")
    parser.add_argument("--project-root", required=True)
    parser.add_argument(
        "--output",
        default="",
        help="Output HTML path (default: <project>/pending-board.html)",
    )
    args = parser.parse_args()
    root = Path(args.project_root)
    out = Path(args.output) if args.output else root / "pending-board.html"
    html_out = render_pending_html(root)
    out.expanduser().resolve().write_text(html_out, encoding="utf-8")
    print(json.dumps({"output": str(out.expanduser().resolve())}, ensure_ascii=False))


if __name__ == "__main__":
    import json

    main()
