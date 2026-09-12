---
name: fulfillment-card
description: >-
  辅助 Skill：履约条件卡片渲染。读 card-data.json，写出同包「履约条件卡片.html」；
  渲完后自动调用 payment-form 刷新「请款申请.html」。被业务 Skill 1/2/3 显式调用。
  不处理邮件、Tracker、请款入账、变更状态；不拥有请款页 / 出 Excel（归 payment-form）。
disable-model-invocation: true
---

# 履约卡片（fulfillment-card · 辅助 Skill）

**全局原则**：先理解再处理（见 `skill-orchestration`）——只渲染调用方已理解并写入的 `card-data`，不臆造业务数字。

## 界面划分（产品约定）

同包两页 HTML **共用** `card-data`，但是**两个辅助 Skill**：

| 页面 | 文件 | 谁做 |
|------|------|------|
| 履约条件卡片 | `履约条件卡片.html` | **本 Skill** |
| 请款申请页 | `请款申请.html` | **`payment-form`**（本 Skill 渲卡片后自动调用） |

| 谁 | 职责 |
|----|------|
| **Skill 1** | 干净 `card-data` → 调本 Skill；不手写 HTML |
| **本 Skill** | 履约条件卡片 HTML + 质量软提醒；渲完链式调 `payment-form` |
| **payment-form** | 请款申请页 + 一键公司模板 Excel |
| **Skill 2** | 请款业务：提醒、ledger、回写 Tracker |

精调「履约卡片」→ 本 Skill；精调「请款页 / 出 Excel」→ `payment-form`；精调「数据抽得对不对」→ Skill 1。

## 定位

| 做 | 不做 |
|----|------|
| `card-data.json` → `履约条件卡片.html` | 收邮件、改 Tracker |
| 渲完自动调 `payment-form` 刷请款页 | **拥有/精调**请款页或 Excel（归 `payment-form`） |
| 模板校验 + 格式校验（不过则拒出卡） | 请款入账 / ledger（归 Skill 2） |
| **数据质量软提醒**（烂数据仍出卡，但必须提示） | 写 Change Log |
| 付款节点 enrich（读 `.skill/schedule.json`） | |

**调用方**：Skill 1、Skill 2、Skill 3。  
**下游**：`payment-form`（刷请款页）。  
**依赖**：共用库 `project-foundation`（`.cursor/lib/`）。

## 权威文档

- `references/card-template.md` — 履约卡片模板与字段规范
- `assets/fulfillment-card.html` — 履约卡片 HTML 真源
- 请款页 / Excel → `.cursor/skills/payment-form/`

## 标准命令

```bash
python3 .cursor/skills/fulfillment-card/scripts/render_card.py \
  --package-dir "/path/to/{序号}_{采购包}_{供应商}/" \
  --patch '{"supplier_name":"…", …}'
```

空 patch 仅重渲染卡片并刷请款页：`--patch '{}'`

**只**重刷请款页（不改卡片）：

```bash
python3 .cursor/skills/payment-form/scripts/sync_claim_form.py \
  --package-dir "/path/to/{序号}_{采购包}_{供应商}/"
```

## 输出

| 字段 | 说明 |
|------|------|
| `card_path` | `履约条件卡片.html` |
| `card_data_path` | `card-data.json` |
| `claim_form_path` | `请款申请.html`（已由 payment-form 同步） |
| `needs_claim_sync` | 恒为 `false`（请款页已刷完） |
| `quality_ok` / `quality_warnings` | 质量软提醒（只在卡片顶栏） |
| `did` | `fulfillment-card.render`、`payment-form.sync` |

质量提醒**不**写入 `pending.json`。

## 调用方后续动作

| 调用方 | 渲染后 |
|--------|--------|
| Skill 1 / 3 | 有 `claim_form_path` 即完成；**不要**再手跑 `payment-form` sync |
| Skill 2 | 消费请款页；改 `card-data` 后须再调本 Skill（或只要刷页则只调 payment-form） |

总规则：`.cursor/skills/skill-orchestration/SKILL.md`。

## 禁止

- ❌ 手改 `履约条件卡片.html`
- ❌ 在本 Skill 内维护请款页模板 / Apple Excel
- ❌ 业务 Skill 在已有 `claim_form_path` 时再单独 sync 请款页

## 评测（判卷）

规则真源：`evals/GRADING_RULES.md`（履约卡片格式/质量；请款页内容归 payment-form 精调）。

```bash
python3 .cursor/skills/fulfillment-card/scripts/run_all_evals.py
```
