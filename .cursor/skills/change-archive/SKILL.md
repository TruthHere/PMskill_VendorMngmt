---
name: change-archive
description: 变更存档（Skill 3 · change-archive）。只做变更归档与状态推进：维护 Change Log（CSV），按 COD→PMI→技术审核中→技术确认→商务确认→商务金额确认→Change PO 下发更新状态（可手改为已取消），归档邮件/附件。不定价、不核定变更金额；不修改采购包 Tracker；不写入履约卡片。务必在用户或其他 Skill 提到变更、COD、PMI、Change Log、变更台账、变更存档、技术文件审核、技术确认、商务金额确认、CP Confirm、Change PO、change_po_deferred、已取消、变更序号/COT、04_变更洽商时使用。
---

# 变更存档（Skill 3）

一句话：把变更邮件变成 **Change Log + 双归档**。  
**不定价、不改采购包 Tracker、不写履约卡片。**

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
python3 .cursor/skills/change-archive/scripts/handle_change_email.py \
  --project-root "/path/to/project" \
  --eml "/path/to/msg.eml" \
  --route-json "/path/to/route.json"
```

评测：`python3 .cursor/skills/change-archive/scripts/run_all_evals.py`

## 硬规则（短）

1. **先理解再处理**：见 `skill-orchestration`。先认清阶段与变更序号再推状态；吃不准 → pending。
2. **Change Log 权威**：`{项目名}_change_log.csv`；模板 `assets/change_log.template.csv`。主键 = 变更序号 + 采购包名称。**允许你手改 CSV**（改状态、金额、备注、写成「已取消」都行）。Skill 3 **只做邮件驱动的写入**，不因发现手改再二次判断、不纠偏、不重算。
3. **里程碑**（与采购包 Tracker 同语义）：每节点一列，单元格有时间戳=已达成（首次锁定）。列序：`COD已发出` → … → `Change PO下发` → `已取消`。`当前状态` 只作总览。优先用邮件 Date。
4. **已取消**：终态侧枝。你手改 `当前状态=已取消`（或填「已取消」列）后，后续变更邮件**仍可归档**，但**不再推进状态/金额**。前序戳保留当历史。
5. **顾问确认 ≡ 技术确认**：不另设顾问确认列/阶段。
6. **先技术后商务**：技术确认前不进商务；乱序 → pending，禁止跳级硬推。
7. **金额**：预估/最终均为**不含税**，原样转录；不定价、不自算。
8. **不碰采购包 Tracker、不写履约卡片**：只改 Change Log + 归档。现金流 / 请款页直接读本台账的「最终确认金额」。
9. **不加「是否请款」**：变更与请款分开；Skill 4 读 Change Log 进「已确认变更」；请款侧用勾选「是否含变更」复核。
10. **编排**：mail-inbox 已分类则不要再发明分类；`handle_change_email` 已做完的不要同一回合手搓。总表见 `skill-orchestration`。

细则：`references/change-log-schema.md`、`email-stages.md`、`folder-rules.md`。

## 步骤（邮件 → 动作）

| 阶段 | 识别 | 主要动作 |
|------|------|----------|
| COD | COD / Change Order | 建行、`COD已发出` 戳、抽预估/标题/时间影响、双归档 |
| PMI | PMI / 指令 | `PMI已发出` 戳、归档（须已有 COD 行） |
| 技术首提 | submittal / 图纸送审 | `技术文件提交`+`技术审核中`；图纸 04+02 |
| 技术确认 | approved / no further comment | `技术确认` 戳 |
| 商务确认 | 转 QS / commercial | `商务确认` 戳（须已有技术确认） |
| 商务金额确认 | CP confirm / 最终金额 | 写最终金额到 Change Log |
| Change PO | `(Change PO)` 等 | `Change PO下发`；关闭历史 deferred pending |
| 已取消 | **手改** CSV（非邮件主路径） | 标终态；之后邮件只归档不推进 |

中间扯皮意见：不改当前状态（专用邮箱通常也收不到）。

## 产出

- `{项目名}_change_log.csv`
- `{包}/04_变更洽商/`、`07_往来文件/`（图纸另入 `02_图纸/`）
- `pending.json`：包不清、序号不清、乱序、金额不清等

## 检查清单

- [ ] 主键（序号 + 包）正确；状态未回退；先技术后商务（已取消除外）
- [ ] 对应里程碑列已盖戳（含 COD/PMI）；未覆盖旧戳
- [ ] 已取消行：后续邮件未把状态改回去
- [ ] 金额不含税且 CSV 未串列
- [ ] 邮件 07+04、图纸 04+02 已双归档
- [ ] 未改采购包 Tracker、未写履约卡片 `change_items`

## 相关 Skill

| 需要时 | 去哪 |
|--------|------|
| 编排 | `skill-orchestration` |
| 收信分发 | `mail-inbox` |
| 基建 / Tracker | `.cursor/lib/project-foundation`（共用库，不是 Skill） |
| 出 HTML | `fulfillment-card`（**不**由本 Skill 触发） |
| 履约（非变更） | `contract-fulfillment-struct` |
| 请款 | `payment-request` |
| 现金流 | `cashflow-forecast`（读 Change Log） |
