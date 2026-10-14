# 现金流预测 Schema

真源：`.skill/cashflow_forecast.json`（`build_forecast.py --write`）  
给人看的主产物：`{项目名}_Cash Flow Forecast.xlsx`（表结构见 `xlsx-layout.md`）

## 顶层

```json
{
  "as_of": "2026-09-06",
  "currency": "CNY",
  "tax_basis": "excl_tax",
  "payment_lag_days": 30,
  "tail_months": 1,
  "summary": { },
  "calendar": { "start_month": "2026-01", "end_month": "2027-01", "months": [] },
  "packages": [ ],
  "monthly": [ ],
  "line_items": [ ],
  "pending": [ ],
  "warnings": [ ],
  "sources": [ { "kind": "tracker", "label": "采购包 Tracker（CSV）", "rel": "…", "mtime": "…", "sha256": "…" } ]
}
```

## packages（Excel 每一行）

| 字段 | 说明 |
|------|------|
| `seq` / `package` / `supplier` | 序号、采购包、供应商 |
| `amount_excl_tax` | Tracker 合同金额（不含税） |
| `changes_excl_tax` | **已确认变更合计**（每次跑预测重算；来自 Change Log「最终确认金额」，跳过已取消；不手填、不读「是否请款」） |
| `po_number` | card-data 的 PO 号 |
| `payment_terms` | 请款条件，如 `预付款 10%；到货 30%；验收 60%` |
| `pending_excl_tax` | 有金额但缺出账日 |
| `months` | `{ "2026-09": { "expected": 300000, "actual": 0 } }` |

## line_items

| 字段 | 说明 |
|------|------|
| `expected_amount_excl_tax` | **应请**：合同比例（尾款含变更） |
| `actual_amount_excl_tax` | **实请**：该节点已在 Tracker「下一付款节点」之前时的金额 |
| `planned_cash_out_month` | 应请落入的月份（完成日 + 30 天） |
| `actual_month` | 实请落入的月份（用进度窗口日，不读 payment_ledger） |

已付款节点：应请仍按计划月，实请按实际请款月，方便对照拖期。

## 时间轴

从项目开始（`project.json` 的 `start_date`，否则进度/请款最早日期）到项目结束，**再多一个月**（`tail_months`，默认 1）。

## 金额规则

1. 合同基数：Tracker `金额不含税`
2. **已确认变更**：读 Skill 3 Change Log（有「最终确认金额」、非已取消）；本 Skill 每次 `--write` 汇总进「已确认变更」列，并默认加在**尾款应请**上（预测口径：已确认的变更迟早要出账）
3. 应请：`基数 × pct`；最后一笔 + 已确认变更
4. 实请：Tracker 已请完的节点（「下一付款节点」之前）；金额来自合同节点，不读 payment_ledger。请款页「是否含变更」只是复核标记，**不**用来拆现金流

**边界**：变更台账不加「是否请款」。业务上「已确认 → 对应请款应含变更」靠 PM/供应商在请款金额里体现 + 请款页勾选提醒；现金流只保证「已确认变更金额」列与变更数据一致。

## 日期规则（应请锚点）

1. `cashflow_overrides.json`
2. `payment_node.milestone`
3. `critical_nodes.window_end`
4. `schedule_window`
5. 条件推断（PO + N 天）
6. 皆无 → pending，不进月列
