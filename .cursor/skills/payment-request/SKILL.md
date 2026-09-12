---
name: payment-request
description: >-
  请款（Skill 2 · payment-request）。按 schedule-critical-nodes 的 window_end 提前约两周，
  只提醒每包「下一笔待请」；追踪请款五步（供应商来请款 → 发QS → QS确认金额 → 发客户
  → 客户批复），状态只写采购包 Tracker；仅客户批复后计入已请金额。03_请款记录只归档邮件/
  Excel/附件，不另开流水账。消费同包请款申请.html（payment-form 生成）。务必在用户提到
  请款提醒、请款记录、PAYMENT NO、03_请款记录、请款进度、下一笔待请、QS核对、客户批复、
  payment-request、Skill 2 请款时使用。精调请款页/出 Excel → 用 payment-form，勿用本 Skill。
---

# 请款（Skill 2 · payment-request）

**业务 Skill**：Skill 2。负责请款**状态**（提醒、五步、客户批复后改已请）与**存档**。  
**请款不要第二本账**：采购包 Tracker 是唯一状态；`03_请款记录/` 是档案柜。

**全局原则**：先理解再处理（见 `skill-orchestration`）——先看清这封信在五步的哪一步，再写 Tracker。

## 状态口径（对人）

| 原则 | 做法 |
|------|------|
| **Tracker 唯一状态** | 已请 / 待请 / 下一付款节点 / 请款进度 —— 都只写总表这一行 |
| **只显示下一笔待请** | 提醒与对话：每包只报 Tracker「下一付款节点」 |
| **五步都要记** | 记在「请款进度」；细则 `references/claim-stages.md` |
| **真正完成 = 客户批复** | 只有批复才加算「已请金额」、进度改 `无在办`、切下一节点 |
| **03 只归档** | 邮件、批复、请款 Excel、附件；不维护 `payment_ledger.json` |
| **跳级脚本拦** | 没走完前面的步就想批复 → pending；补录才 `--allow-skip` |

## 界面划分

| 页面 / 产物 | 归谁 |
|-------------|------|
| `履约条件卡片.html` | **fulfillment-card** |
| `请款申请.html`、浏览器一键下 Excel | **payment-form**（发给客户前用） |
| Tracker 请款四列、提醒、邮件推进、03 归档 | **本 Skill（Skill 2）** |
| 付款条件写入卡片 | **Skill 1** |

## 权威参考

| 文件 | 何时读 |
|------|--------|
| `references/claim-stages.md` | 五步箭头、谁推、是否占用 |
| `references/tracker-payment.md` | Tracker 四列 + 03 档案柜 |
| `references/bot-reminders.md` | 14 天提醒话术 |
| `references/checklist-by-node.md` | 节点支持文件（给人看） |
| `payment-form/references/claim-form.md` | 请款页/Excel 字段 |

## 三功能

```
critical_nodes.window_end + Tracker 下一付款节点
        │
        ▼
① 扫描提醒（lead-days=14）→ 机器人问 PM
        │
        ▼
② 供应商请款 → Tracker「请款进度」= 已收到（不占已请）
        → 发QS → QS确认 → 打开请款页/Excel → 发客户
        │
        ▼
③ 客户批复 → 已请金额累加；下一节点前进；进度=无在办
        同时把邮件/Excel 副本放进 03_请款记录/
```

### 1. 适时提醒

```bash
python3 .cursor/skills/payment-request/scripts/scan_due_payments.py \
  --project-root "/path/to/project" \
  --lead-days 14 \
  --write
```

### 2. 请款页（消费，不生成）

```bash
python3 .cursor/skills/fulfillment-card/scripts/render_card.py \
  --package-dir "/path/to/01_xxx_Vendor" \
  --patch '{}'
```

只刷请款页：`payment-form/scripts/sync_claim_form.py`。

### 3. 推进请款步骤（写 Tracker + 可选归档）

```bash
python3 .cursor/skills/payment-request/scripts/record_payment.py \
  --package-dir "/path/to/01_xxx_Vendor" \
  --node "到货 / Delivery" \
  --amount-excl-tax 300000 \
  --status qs_sent
```

客户批复：`--status certified`（必填金额）。  
邮箱：`record_payment_email.py`（默认 `vendor_received`，并把 `.eml` 拷进 03）。

## 挂钩

| 对方 | 关系 |
|------|------|
| Skill 1 | 履约；调 fulfillment-card |
| payment-form | 请款页 + Excel；本 Skill 只消费 |
| Skill 3 | 变更；本 Skill 不碰 |
| 现金流 | 只读 Tracker「下一付款节点」之前视为已付 |

## 冒烟

```bash
python3 .cursor/skills/payment-request/scripts/smoke_skill2.py
```

## Agent 清单

- [ ] 是否按 Skill 2 处理（非并入 Skill 1）？
- [ ] 是否只写 Tracker、**没有**再写 payment_ledger？
- [ ] 是否分清五步？未把来信/发客户当成已请完？
- [ ] 客户未批复是否**没有**改已请金额？
- [ ] 附件是否进了 `03_请款记录/`？
- [ ] 跳级是否挂 pending？
- [ ] 请款页是否已由 payment-form 生成？
