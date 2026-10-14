---
name: vendor-card
description: >-
  辅助 Skill：履约条件卡片渲染。读 card-data.json，写出同包「履约条件卡片.html」；
  渲完后自动调用 payment-sheet 刷新「请款申请.html」（无客户请款单模板时写出未启用页，不拿样例表充数）。
  不处理邮件、Tracker、请款入账、变更状态；不拥有请款页 / 出 Excel（归 payment-sheet）。
disable-model-invocation: true
---

# 履约卡片（vendor-card · 辅助 Skill）

**全局原则**：先理解再处理（见 `skill-orchestration`）——只渲染调用方已理解并写入的 `card-data`，不臆造业务数字。

## 编排硬规则（摘要）

跨 Skill / 进度 / 合同 PDF / 邮件分发 → 先读 `<skills-root>/skill-orchestration/ALWAYS.md`（细节见同目录 `README.md`）。
单独使用功能 Skill 时禁止擅自串联履约/请款；脚本已串完的不要双跑；时间线对人只有 `项目档案/00_进度计划/关键节点时间线.html` 一份。
`skills-root` = 本机 Skills 安装根（WorkBuddy 常见 `~/.workbuddy/skills/`）。命令写成 `python3 <skills-root>/<技能名>/scripts/…`。

## 界面划分（产品约定）

同包两页 HTML **共用** `card-data`，但是**两个辅助 Skill**：

| 页面 | 文件 | 谁做 |
|------|------|------|
| 履约条件卡片 | `履约条件卡片.html` | **本 Skill** |
| 请款申请页 | `请款申请.html` | **`payment-sheet`**（本 Skill 渲卡片后自动调用） |

| 谁 | 职责 |
|----|------|
| **Skill 1** | 干净 `card-data` → 调本 Skill。数据抽得对不对归 Skill 1 |
| **本 Skill** | 履约卡片 HTML。改 `assets/vendor-card.html` 后重跑，不手改生成出来的 html。模板校验不过则拒出卡；烂数据仍出卡，但必须在顶栏提示。付款节点可按 `schedule.json` 补全。渲完链式调 `payment-sheet` |
| **payment-sheet** | 请款申请页 + 一键公司模板 Excel |
| **Skill 2** | 请款业务：提醒、ledger、回写 Tracker |

**调用方**：Skill 1、Skill 2、Skill 3。  
**下游**：`payment-sheet`（刷请款页）。  
**依赖**：共用库 `project-foundation`（`<skills-root>/project-foundation`）。

## 权威文档

- `references/card-template.md` — 履约卡片模板与字段规范
- `assets/vendor-card.html` — 履约卡片 HTML 真源
- 请款页 / Excel → `<skills-root>/payment-sheet/`

## 标准命令

```bash
python3 <skills-root>/vendor-card/scripts/render_card.py \
  --package-dir "/path/to/{序号}_{采购包}_{供应商}/" \
  --patch '{"supplier_name":"…", …}'
```

空 patch 仅重渲染卡片并刷请款页：`--patch '{}'`

直接跑即可。不要为了找到请款页脚本去拼 PYTHONPATH、也不要改 sys.path 绕过。

**只**重刷请款页（不改卡片）：

```bash
python3 <skills-root>/payment-sheet/scripts/sync_claim_form.py \
  --package-dir "/path/to/{序号}_{采购包}_{供应商}/"
```

## 输出

| 字段 | 说明 |
|------|------|
| `card_path` | `履约条件卡片.html` |
| `card_data_path` | `card-data.json` |
| `claim_form_path` | `请款申请.html`（有模板则填写页；无模板则「未启用」提醒页） |
| `payment_form_enabled` | 项目是否已认请款单模板 |
| `payment_form_notice` | 未启用时的提醒原文 |
| `needs_claim_sync` | 恒为 `false`（请款页已刷完或已写未启用页） |
| `quality_ok` / `quality_warnings` | 质量软提醒（只在卡片顶栏） |
| `did` | `vendor-card.render` + `payment-sheet.sync` 或 `payment-sheet.disabled` |

质量提醒**不**写入 `pending.json`。

## 调用方后续动作

| 调用方 | 渲染后 |
|--------|--------|
| Skill 1 / 3 | 有 `claim_form_path` 即完成；**不要**再手跑 `payment-sheet` sync。若 `did` 含 `payment-sheet.disabled`，把「还没有请款单模板，请款单生成尚未启用」告诉用户 |
| Skill 2 | 消费请款页；改 `card-data` 后须再调本 Skill（或只要刷页则只调 payment-sheet） |

## 评测（判卷）

规则真源：`evals/GRADING_RULES.md`（履约卡片格式/质量；请款页内容归 payment-sheet 精调）。

```bash
python3 <skills-root>/vendor-card/scripts/run_all_evals.py
```
