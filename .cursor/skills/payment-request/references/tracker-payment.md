# Tracker 请款章节 + 03 档案柜

**请款不要第二本账。** 采购包 Tracker 是唯一状态；`03_请款记录/` 只存档案。

## Tracker 请款四列（真相）

| 列名 | 内部键 | 含义 |
|------|--------|------|
| **已请金额** | `claimed_amount_excl_tax` | 客户已批复累计（不含税）。未批复前不加算 |
| **待请款金额** | `remaining_claim_amount_excl_tax` | 合同不含税 − 已请金额 |
| **下一付款节点** | `next_payment_node` | 下一笔待请的节点名；批复后切到下一节点 |
| **请款进度** | `payment_progress` | 当前五步人话，如 `已发QS核对 · 到货 / Delivery`；无在办写 **`无在办`** |

五步码 ↔ 进度文案见 `claim-stages.md`。脚本用进度列解析当前步，跳步继续拦。

## 03_请款记录（档案柜，不是流水账）

```
{package_dir}/03_请款记录/
  YYYYMMDD-HHMMSS_PAY2_vendor_received_xxx.eml   # 往来邮件副本
  YYYYMMDD-HHMMSS_PAY2_response_claim_response.json
  PAYMENT_NO_*.xlsx                              # payment-form 出的请款单
  （可选手动放入：客户批复扫描件、附件）
```

- **不要**再维护 `payment_ledger.json` 当正式请款记录（若旧文件仍在，脚本会忽略）
- Skill 2 入账 / 提醒 / 下一笔待请 → **只听 Tracker**
- 请款申请页 / 公司 Excel → **payment-form**（Skill 2 不生成）

## 写入时机

| 动作 | Tracker |
|------|---------|
| 供应商来请款 / 发QS / QS确认 / 发客户 | 更新「请款进度」+「下一付款节点」（仍为本笔）；**不动**已请金额 |
| 客户批复 | 已请 += 本期金额；待请重算；下一节点切下一笔；进度 → `无在办` |
| 退回/驳回 | 进度标已退回/已驳回；已请不变 |

代码：`scripts/payment_status.py`、`scripts/record_payment.py`。
