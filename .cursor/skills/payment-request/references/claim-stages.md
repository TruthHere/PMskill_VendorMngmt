# 请款五步（Claim stages）

真正完成 = **客户批复**。前面四步只记过程：写在 Tracker「请款进度」，**不计入「已请金额」**。

## 正向箭头

```
供应商请款已收到
    → 已发QS核对
    → QS已确认金额
    → 已发客户请款
    → 客户已批复
```

| 步 | status | Tracker「请款进度」示例 | 谁推 | 计入已请 |
|----|--------|-------------------------|------|----------|
| 1 | `vendor_received` | `供应商请款已收到 · 到货 / Delivery` | 供应商请款邮件或对话 | 否 |
| 2 | `qs_sent` | `已发QS核对 · …` | PM 说已发 | 否 |
| 3 | `qs_confirmed` | `QS已确认金额 · …` | QS 回信或 PM 转告 | 否 |
| 4 | `client_sent` | `已发客户请款 · …` | PM 说已发客户；页/Excel 是材料 | 否 |
| 5 | `certified` | 写完后改成 **`无在办`**，并切「下一付款节点」 | 客户批复邮件或 PM 声明 | **是** |

无在办（进度列 = `无在办`）时，下一轮须从步骤 1 再开。

退回：`returned` / `rejected` 写在进度列；已请不变；可从步骤 1 或 2 重开。

旧口径：`draft` ≡ 步骤 1；`submitted` ≡ 步骤 4（已发客户，**不是**完成）。

## 跳级

脚本硬拦。无步骤 1 就想客户批复 → pending `payment_claim_out_of_order`。补录才 `--allow-skip`。

## 邮件意图

| intent | 落到 |
|--------|------|
| `payment_claim.inbound` | 步骤 1 |
| `payment_claim.qs_sent` | 步骤 2 |
| `payment_claim.qs_confirm` | 步骤 3 |
| `payment_claim.client_sent` | 步骤 4 |
| `payment_claim.client_approved` | 步骤 5 |
