# 机器人提醒（Skill 2）

先提醒 **PM**，不自动给供应商发催款。

## 扫描

```bash
python3 .cursor/skills/payment-flow/scripts/scan_due_payments.py \
  --project-root "/path/to/project" \
  --lead-days 14 \
  --write
```

- 默认 **`--lead-days 14`**（约提前两周）
- **每包只扫下一笔待请**（卡片顺序里第一个尚未客户批复 `certified` 的节点）× 其 `window_end`
- 产出：`.skill/payment_due.json`（`policy: next_pending_only`）

`urgency`：`due_soon` | `due_today` | `overdue`

## 话术

只报下一笔，不要把后面节点一并催：

```
【请款提醒】{项目} · {包} · {供应商}
下一笔待请：「{节点}」完成时点约 {旬}（{window_end}）。
按合同该节点可请款约 {比例}（不含税，供参考）。
请款号：PAYMENT NO {n}

请回复：
A) 节点已完成 → 打开履约卡片「发起请款」或把 请款申请.html 发给供应商
B) 尚未完成 → 延后，注明预计旬
C) 客户已批复、要记完成 → 转发批复邮件或声明「客户已批复」
```

## pending（可选，写入项目 `.skill/pending.json`，`skill=payment-flow`）

| code | 场景 |
|------|------|
| `payment_due_confirm` | 到点是否允许发起请款 |
| `payment_amount_ambiguous` | 邮件金额/含税不清 |
| `payment_complete_unconfirmed` | 有请款材料但客户尚未批复 |
