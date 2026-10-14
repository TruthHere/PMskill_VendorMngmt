# agent_notes · eval-2 with_skill（Raise PO + 付款指示）

## 结论
BMS / BOSCH 包已推进到 **PO 已发起**；卡片写入 **3 个付款节点**（30% / 60% / 10%）；**金额含税 ¥1,280,000** 已落 Tracker 与卡片。不含税侧缺失 → `pending.tax_rate_uncertain`（符合 Skill 规则）。

## 做了什么
1. 读 `po-flow` Skill；用 `process_email.py` 依次处理 `raise_po.eml`、`payment.eml`。
2. 首轮因履约卡片模板瞬时缺 `{{quality_banner_html}}` 校验失败；模板恢复后重跑两封，成功（JSON 见 `process_email_raise_po.json` / `process_email_payment.json` / `process_result.json`）。
3. 两封 `.eml` 已归档至 `01_BMS_BOSCH/07_往来文件/`。
4. 卡片 `total_amount` 补注「含税」后经 `vendor-card/render_card.py` 重渲染（`quality_ok=true`）。

## 当前状态
| 项 | 值 |
|----|-----|
| 里程碑 | 技术方案已确认 / 商务报价已确认 / **PO 已发起** = 2026-08-01 |
| 金额含税 | 1280000.00（邮件：¥1,280,000 含税） |
| 金额不含税 | 空（pending 问税率） |
| 下一付款节点 | 预付款 / Advance 30% |
| payment_nodes | 预付款 30% · 到货验收 60% · 尾款 10% |
| 交期 | 2026-09-30 |

## Pending
- `tax_rate_uncertain`：仅有含税金额，缺不含税/税率——需 PM 确认后补全。
