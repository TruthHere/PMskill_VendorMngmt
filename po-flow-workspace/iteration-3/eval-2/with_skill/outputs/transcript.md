# transcript

1. Read Skill 1 `po-flow/SKILL.md`（步骤 3 Raise PO → 步骤 4 付款；卡片经 vendor-card 渲染）。
2. 确认工作目录已有 BMS 包（技术方案已确认）+ Tracker + `card-data.json`。
3. 解码 `_mail/raise_po.eml`：SAMPLE / BMS / BOSCH；金额含税 ¥1,280,000；交期 2026-09-30；Raise PO。
4. 解码 `_mail/payment.eml`：预付款 30% / 到货验收 60% / 尾款 10%。
5. `process_email.py --project-root outputs --eml _mail/raise_po.eml` → 首轮模板校验失败（缺 `{{quality_banner_html}}`）；Tracker 已部分写入 PO/金额。
6. 模板可用后重跑 Raise PO → `step3` / `fulfillment.raise_po`；归档往来；`tax_uncertain` → pending。
7. 重跑 `payment.eml` → `step4_payment` / `payment_nodes: 3`；stdout 存 `process_email_*.json` + `process_result.json`。
8. `update_tracker.py --sync-payment-node`；`render_card.py --patch` 总金额标注含税。
9. 写 `agent_notes.md`、本 `transcript.md`。
