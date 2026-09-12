# 现金流人工覆盖

路径：`.skill/cashflow_overrides.json`（可选；不存在则用默认规则）

## 示例

```json
{
  "assumptions": {
    "payment_lag_days": 30
  },
  "overrides": [
    {
      "package": "BMS",
      "payment_no": 3,
      "forecast_date": "2026-12-15",
      "note": "质保期满，与业主口头对齐"
    }
  ]
}
```

## 字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `assumptions.payment_lag_days` | 否 | 覆盖 CLI 默认 30 |
| `overrides[].package` | 是 | 采购包名称（与 Tracker / card-data 一致） |
| `overrides[].payment_no` | 是 | 付款节点序号（1-based，与卡片顺序一致） |
| `overrides[].forecast_date` | 是 | `YYYY-MM-DD`，作为**出账日**（已是 cash out，不再 + lag） |
| `overrides[].note` | 否 | 给人看的备注，写入 `line_items` |

`forecast_date` 在覆盖模式下视为最终出账日，`date_source=override`，`date_confidence=high`。
