---
name: payment-flow
description: >-
  请款（Skill 2 · payment-flow）。按 critical-nodes 的 window_end 提前约两周，
  只提醒每包「下一笔待请」；追踪请款五步（供应商来请款 → 发QS → QS确认金额 → 发客户
  → 客户批复），状态只写采购包 Tracker；仅客户批复后计入已请金额。03_请款记录只归档邮件/
  Excel/附件，不另开流水账。消费同包请款申请.html（payment-sheet 生成）。务必在用户提到
  请款提醒、请款记录、PAYMENT NO、03_请款记录、请款进度、下一笔待请、QS核对、客户批复、
  payment-flow、Skill 2 请款时使用。精调请款页/出 Excel → 用 payment-sheet，勿用本 Skill。
---

# 请款（Skill 2 · payment-flow）

**业务 Skill**：Skill 2。负责请款**状态**（提醒、五步、客户批复后改已请）与**存档**。账只写在下面这张表里。

**全局原则**：先理解再处理（见 `skill-orchestration`）——先看清这封信在五步的哪一步，再写 Tracker。

## 编排硬规则（摘要）

跨 Skill / 进度 / 合同 PDF / 邮件分发 → 先读 `<skills-root>/skill-orchestration/ALWAYS.md`（细节见同目录 `README.md`）。
单独使用功能 Skill 时禁止擅自串联履约/请款；脚本已串完的不要双跑；时间线对人只有 `项目档案/00_进度计划/关键节点时间线.html` 一份。
`skills-root` = 本机 Skills 安装根（WorkBuddy 常见 `~/.workbuddy/skills/`）。命令写成 `python3 <skills-root>/<技能名>/scripts/…`。

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
| `履约条件卡片.html` | **vendor-card** |
| `请款申请.html`、浏览器一键下 Excel | **payment-sheet**（发给客户前用） |
| Tracker 请款四列、提醒、邮件推进、03 归档 | **本 Skill（Skill 2）** |
| 付款条件写入卡片 | **Skill 1** |

## 权威参考

| 文件 | 何时读 |
|------|--------|
| `references/claim-stages.md` | 五步箭头、谁推、是否占用 |
| `references/tracker-payment.md` | Tracker 四列 + 03 档案柜 |
| `references/bot-reminders.md` | 14 天提醒话术 |
| `references/checklist-by-node.md` | 节点支持文件（给人看） |
| `payment-sheet/references/claim-form.md` | 请款页/Excel 字段 |

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
python3 <skills-root>/payment-flow/scripts/scan_due_payments.py \
  --project-root "/path/to/project" \
  --lead-days 14 \
  --write
```

### 2. 请款页（消费，不生成）

```bash
python3 <skills-root>/vendor-card/scripts/render_card.py \
  --package-dir "/path/to/01_xxx_Vendor" \
  --patch '{}'
```

只刷请款页：`payment-sheet/scripts/sync_claim_form.py`。

### 3. 推进请款步骤（写 Tracker + 可选归档）

```bash
python3 <skills-root>/payment-flow/scripts/record_payment.py \
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
| Skill 1 | 履约；调 vendor-card |
| payment-sheet | 请款页 + Excel |
| Skill 3 | 变更台账；本 Skill 不写 |
| 现金流 | 只读 Tracker「下一付款节点」之前视为已付 |

## 冒烟

```bash
python3 <skills-root>/payment-flow/scripts/smoke_skill2.py
```

## Agent 清单

- [ ] 是否分清五步？未把来信/发客户当成已请完？
- [ ] 附件是否进了 `03_请款记录/`？
- [ ] 跳级是否挂 pending？
- [ ] 请款页是否已由 payment-sheet 生成？
