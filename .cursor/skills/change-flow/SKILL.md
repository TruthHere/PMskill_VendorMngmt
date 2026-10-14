---
name: change-flow
description: 变更存档（Skill 3 · change-flow）。只做变更归档与状态推进：维护 Change Log（CSV），按 COD→PMI→技术审核中→技术确认→商务确认→商务金额确认→Change PO 下发更新状态（可手改为已取消），归档邮件/附件。不定价、不核定变更金额；不修改采购包 Tracker；不写入履约卡片。务必在用户或其他 Skill 提到变更、COD、PMI、Change Log、变更台账、变更存档、技术文件审核、技术确认、商务金额确认、CP Confirm、Change PO、change_po_deferred、已取消、变更序号/COT、04_变更洽商时使用。
---

# 变更存档（Skill 3）

一句话：把变更邮件变成 **Change Log + 双归档**。做到哪为止，见下面的表。

## 编排硬规则（摘要）

跨 Skill / 进度 / 合同 PDF / 邮件分发 → 先读 `<skills-root>/skill-orchestration/ALWAYS.md`（细节见同目录 `README.md`）。
单独使用功能 Skill 时禁止擅自串联履约/请款；脚本已串完的不要双跑；时间线对人只有 `项目档案/00_进度计划/关键节点时间线.html` 一份。
`skills-root` = 本机 Skills 安装根（WorkBuddy 常见 `~/.workbuddy/skills/`）。命令写成 `python3 <skills-root>/<技能名>/scripts/…`。

## 做什么 / 不做什么

| 做 | 不做 |
|----|------|
| 消费 `change.*`（经 mail-inbox）→ 更新 Change Log | 改采购包 Tracker → Skill 1 |
| 邮件 07+04、图纸 04+02 双归档 | 请款入账 → Skill 2 |
| 商务金额确认：只写台账「最终确认金额」 | 代发 COD/PMI/PO；IMAP 收信 |
| 处理 `change.change_po`；关闭历史 `change_po_deferred` | 写入履约卡片 / `change_items` |
| 歧义进 `pending.json`，再问人 | 变更影响连锁分析；自算核定金额 |

前置：项目已初始化（有 `.skill/project.json` + 采购包）。不另建项目、不另开邮箱。

## 主路径

```bash
python3 <skills-root>/change-flow/scripts/handle_change_email.py \
  --project-root "/path/to/project" \
  --eml "/path/to/msg.eml" \
  --route-json "/path/to/route.json"
```

评测：`python3 <skills-root>/change-flow/scripts/run_all_evals.py`

## 硬规则（短）

1. **先理解再处理**：见 `skill-orchestration`。先认清阶段与变更序号再推状态；吃不准 → pending。线程回信只看最新一段（引用里的 COD/RFP 不算本封意图），见 mail-inbox 意图表「线程回信怎么判」。
2. **Change Log 权威**：机读 `.skill/change_log.csv`；给人看 `{项目名}_Change Log.xlsx`。模板 `assets/change_log.template.csv`。主键 = 变更序号 + 采购包名称。**允许你手改 CSV（在 .skill）或对照 Excel**。Skill 3 **只做邮件驱动的写入**，不因发现手改再二次判断、不纠偏、不重算。
3. **里程碑**（与采购包 Tracker 同语义）：每节点一列，单元格有时间戳=已达成（首次锁定）。列序：`COD已发出` → … → `Change PO下发` → `已取消`。`当前状态` 只作总览。优先用邮件 Date。
4. **已取消**：终态侧枝。你手改 `当前状态=已取消`（或填「已取消」列）后，后续变更邮件**仍可归档**，但**不再推进状态/金额**。前序戳保留当历史。
5. **顾问确认 ≡ 技术确认**：不另设顾问确认列/阶段。
6. **先技术后商务**：技术确认前不进商务；乱序 → pending，禁止跳级硬推。
7. **金额**：预估/最终均为**不含税**，原样转录。现金流和请款页读「最终确认金额」，本 Skill 不写它们的账。
8. **不加「是否请款」**：变更与请款分开；现金流预测读 Change Log 进「已确认变更」；请款侧用勾选「是否含变更」复核。
9. **分类**：以 mail-inbox 的意图为准，不另造分类器。

细则：`references/change-log-schema.md`、`email-stages.md`、`folder-rules.md`。

## 步骤（邮件 → 动作）

| 阶段 | 识别 | 主要动作 |
|------|------|----------|
| COD | COD / Change Order | 建行、`COD已发出` 戳、抽短标题/详细说明/预估/时间影响、双归档 |
| PMI | PMI / 指令 | `PMI已发出` 戳、归档（须已有 COD 行） |
| 技术首提 | submittal / 图纸送审 | `技术文件提交`+`技术审核中`；图纸 04+02 |
| 技术确认 | approved / no further comment | `技术确认` 戳 |
| 商务确认 | 转 QS / commercial | `商务确认` 戳（须已有技术确认） |
| 商务金额确认 | CP confirm / 最终金额 | 写最终金额到 Change Log |
| Change PO | `(Change PO)` 等 | `Change PO下发`；关闭历史 deferred pending |
| 已取消 | **手改** CSV（非邮件主路径） | 标终态；之后邮件只归档不推进 |

中间扯皮意见：不改当前状态（专用邮箱通常也收不到）。

## 产出

- `.skill/change_log.csv`（机读）+ `{项目名}_Change Log.xlsx`（项目根，给人看）
- `{包}/04_变更洽商/`、`07_往来文件/`（图纸另入 `02_图纸/`）
- `pending.json`：包不清、序号不清、乱序、金额不清等

## 检查清单

- [ ] 主键（序号 + 包）正确；状态未回退；先技术后商务（已取消除外）
- [ ] 对应里程碑列已盖戳（含 COD/PMI）；未覆盖旧戳
- [ ] 已取消行：后续邮件未把状态改回去
- [ ] 金额不含税且 CSV 未串列
- [ ] 邮件 07+04、图纸 04+02 已双归档

## 相关 Skill

| 需要时 | 去哪 |
|--------|------|
| 编排 | `skill-orchestration` |
| 收信分发 | `mail-inbox` |
| 基建 / Tracker | `<skills-root>/project-foundation`（共用库，不是 Skill） |
| 出 HTML | `vendor-card`（**不**由本 Skill 触发） |
| 履约（非变更） | `po-flow` |
| 请款 | `payment-flow` |
| 现金流 | `cashflow`（读 Change Log） |
