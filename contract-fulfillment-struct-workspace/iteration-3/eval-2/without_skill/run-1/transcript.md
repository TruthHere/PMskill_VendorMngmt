# Transcript — eval-2 / without_skill / run-1

- 读取 `raise_po.eml`：BMS / BOSCH，含税 ¥1,280,000，交期 2026-09-30 → 归档往来文件；Tracker 写金额含税、交期、PO 已发起；卡片更新金额与交期。
- 读取 `payment.eml`：预付款 30% / 到货验收 60% / 尾款 10% → 归档；卡片写入 3 个付款节点；Tracker「下一付款节点」= 预付款 30%。
- 产出：`card-data.json`、`履约条件卡片.html`、`请款申请.html`、Tracker csv/xlsx、`outputs/agent_notes.md`。
- 方式：baseline 手工处理，未用合同履约 Skill。
