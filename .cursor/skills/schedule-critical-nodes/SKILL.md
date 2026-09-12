---
name: schedule-critical-nodes
description: >-
  进度计划关键节点分析（Agent 主导）。读懂粗粒度进度（Excel/CSV；.mpp / Project XML
  须先经 schedule-mpp-excel → *_schedule.csv），按采购包推理到货/厂验/安装/验收等
  完成时点，写入 .skill/schedule.json 的 critical_nodes；请款对齐用 window_end，
  对人默认报「月+上中下旬」。务必在用户提到进度计划、甘特、Schedule 基座、关键节点、
  到货/厂验/安装/验收倒排、请款完成时点、critical_nodes、请款时间线时使用。
  可单独使用；系统内与履约/建包同步见 skill-orchestration。
---

# 进度计划关键节点分析（Agent 主导）

**全局原则**：先理解再处理（见 `skill-orchestration`）。  
本 Skill 的主路径是 **Agent 读懂进度表 → 推理节点 → 落盘**；脚本只做校验、写文件、可选时间线。  
**禁止**把关键词字典/自动倒排脚本当成「已经理解了进度」。

## 权威文档

- `references/node-taxonomy.md` — 节点码表与包类型模板（Agent 推理时对齐 `node_code`）
- `references/matching-rules.md` — **Agent 推理规则**（归属、explicit/inferred、倒排思路、冲突）；关键词表仅作弱提示
- `references/schedule-io.md` — **输出契约**（JSON / 摘要）
- `references/presentation.md` — 完成时点 / 旬粒度 / **时间线视觉与交互**（改 HTML 必读）
- `.cursor/skills/schedule-mpp-excel/SKILL.md` — 收到 `.mpp` / Project XML 时必先调用
- 系统内多 Skill 协作 → `.cursor/skills/skill-orchestration/SKILL.md`

## 谁干什么

| 角色 | 职责 |
|------|------|
| **Agent** | 读源表与采购包清单；判断每行语义与包归属；按模板补全缺失关键节点；写清 `basis` / `confidence`；吃不准 → `pending` / `needs_confirm` |
| **脚本** | 校验字段与日期；合并写入 `.skill/schedule.json`；可选 Markdown 摘要与时间线 HTML；建包后**只重渲时间线**（不覆盖已有推理） |

可选脚本 `analyze_schedule.py`：仅在要**粗草稿**或无 Agent 时使用；产出须经 Agent 审过再当定稿。默认主路径**不要**依赖它。

## 已定产品原则（必须遵守）

1. **主交付**：结构化数据（`.skill/schedule.json`）。需要可视化时用时间线 HTML，**视觉必须遵守** `presentation.md` §4（禁止糙默认模板）。
2. **完成时点语义**：关键节点回答「何时完成（可请款）」。机器可留 `window_start`/`window_end`，**对齐与口头汇报一律以 `window_end` 为准**。
3. **对人默认旬粒度**：`YYYY年M月上/中/下旬`；JSON 仍存 ISO 日。
4. **时间线（可选）**：左侧采购包 sticky + 右侧横滑；节点为完成时点圆点；**默认叠加春节/五一/十一停工色带**（`cn_holidays.py`）。脚本：`write_critical_nodes.py --write-timeline` / `render_timeline.py` / `sync_schedule_timeline.py`。PM 可在页面上改完后「保存全部修改」（覆盖 HTML + `.skill/schedule.json`）；也可用 `apply_timeline_edits.py` 写回。
5. **MPP 链路**：不直读 `.mpp` → 先 `schedule-mpp-excel` → `*_schedule.csv` → 本 Skill。
6. **低置信须确认**：吃不准就 `pending` / `needs_confirm`，不静默当定稿。
7. **不准用字典冒充理解**：任务名各异；用上下文推理，关键词表最多当联想，不能当唯一判决。
8. **总包 ≠ 抽象项目级**：整盘公共节点挂「总包」；各采购包只挂请款相关节点。包级「验收」默认对齐总包/客户验收前后。

## 能力边界

- **做**：理解进度表 → 归属采购包 → 匹配/推断关键节点 → 结构化契约 + 可选摘要/时间线（时间线视觉见 `presentation.md`）
- **不做**：另做履约看板产品；不写合同付款比例；不渲染履约卡片；**不直读**原生 `.mpp`
- **定位**：可单独使用；系统内何时同步卡片/建包见编排 Skill

## 输入

| 优先 | 说明 |
|------|------|
| `.xlsx` / `.csv` | 一等公民；表头见 `.cursor/lib/project-foundation/references/schedule-csv-schema.md` |
| `.mpp` / Project XML | **必须先**走 `schedule-mpp-excel` → `{stem}_schedule.csv` |
| 采购包清单 | Tracker CSV，或对话/JSON 中的包名+类型 |

最低列：任务/里程碑名称、开始、结束；可选采购包/专业。

## 输出

唯一真源：`{project_root}/.skill/schedule.json`（`milestones` + `critical_nodes` + `pending`）。  
本 Skill 的 pending **只写这份**；禁止写入项目 `.skill/pending.json`（脚本会硬拦）。

可选：`.skill/critical_nodes.md`；时间线 HTML（见 `presentation.md`）。

字段语义见 `references/schedule-io.md`。`source`：`explicit` | `inferred` | `aligned`。

## 工作流（Agent 主路径 · 必须遵守）

1. 确认项目根；收集进度文件与采购包列表（含 `package_type`）
2. 若源是 `.mpp` / Project XML：先执行 `schedule-mpp-excel`，再用 `*_schedule.csv`
3. **阅读**进度表全文（或足够上下文）：搞清项目级锚点、各包粗条/细节点、中英混写含义——**先理解**
4. 阅读 `node-taxonomy.md`、`matching-rules.md`、`presentation.md`（若尚未加载）
5. **推理**并整理 `critical_nodes` + `pending`（按包类型模板；完成时点用 `window_end`；依据写进 `basis`）
6. **落盘**：调用 `write_critical_nodes.py`（校验 + 写入；可选 `--write-md` / `--write-timeline`）
7. 汇报：节点数、`inferred` 数、`pending`；对人日期用旬；强调**完成时点**
8. **单独使用到此为止**。系统内后续见 `skill-orchestration`

### 标准命令（落盘）

```bash
python3 .cursor/skills/schedule-critical-nodes/scripts/write_critical_nodes.py \
  --project-root "/path/to/project" \
  --nodes-json "/path/to/critical_nodes_draft.json" \
  --source "项目档案/00_进度计划/project_schedule.csv" \
  --write-md \
  --write-timeline
```

### PM 在时间线上改完之后（本地 HTML，给所有人用）

**日常用法**（不需要命令行、不需要黑窗口）：

1. 双击打开 `项目档案/00_进度计划/关键节点时间线.html`
2. 点「编辑」→ 可连续改多个采购包的节点 / 待确认（只需标「有未保存的修改」，**不必每改一次就保存**）
3. 全部改完后点一次「保存全部修改」（或点「完成」时按提示保存）→ 浏览器下载/另存：
   - `关键节点时间线.html`（**用它覆盖原来的同名文件**）
   - `schedule.json`（放进项目 `.skill/` 文件夹，覆盖原文件；给 Skill / 请款等用）
4. 下次直接再双击那个 HTML，就是改过之后的样子

可选：Chrome 若弹出「保存文件」对话框，直接选原路径覆盖即可，比先下到「下载」再搬更省事。

**高级（可选）**：若希望点保存立刻写进项目、不经过下载，可用 `serve_timeline.py`（会开本地网页）。普通人不必用。

`--nodes-json` 可为：

- 仅 `critical_nodes` 数组；或
- 含 `critical_nodes` / `pending` / `packages` / `milestones` 的对象

有 `--source` 时：脚本从源表刷新 `milestones[]`（不据此自动发明节点）。

仅重渲染时间线（已有 `schedule.json`）：

```bash
python3 .cursor/skills/schedule-critical-nodes/scripts/render_timeline.py \
  --project-root "/path/to/project"
```

### 建包后同步（系统内 · 脚本）

`sync_schedule_timeline.py`：**有已有 `critical_nodes` 时只重渲时间线，不重跑字典分析、不覆盖 Agent 结果**。  
无节点且无进度源 → `skipped`。若需粗草稿才加 `--draft-analyze`（须后续 Agent 审定）。

```bash
python3 .cursor/skills/schedule-critical-nodes/scripts/sync_schedule_timeline.py \
  --project-root "/path/to/project" \
  --package-name "BMS" \
  --package-dir "/path/to/01_BMS_Vendor"
```

### 可选：自动草稿（非主路径）

```bash
python3 .cursor/skills/schedule-critical-nodes/scripts/analyze_schedule.py \
  --project-root "/path/to/project" \
  --source "…/project_schedule.csv" \
  --write-md
```

输出仅作草稿；Agent 必须审改后再经 `write_critical_nodes.py` 定稿（或直接改 `schedule.json` 再 `--validate`）。

## 样例

- `samples/explicit/` — 计划已写明到货/安装（供 Agent 练习与草稿对照）
- `samples/coarse/` — 仅有专业粗条，需推理
- `evals/evals.json` — 评测提示（验收以 Agent 理解 + 契约为准）
