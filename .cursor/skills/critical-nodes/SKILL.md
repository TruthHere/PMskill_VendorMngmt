---
name: critical-nodes
description: >-
  进度计划关键节点分析（Agent 主导）。读懂粗粒度进度（Excel/CSV；.mpp / Project XML
  须先经 mpp-to-excel → *_schedule.csv），按采购包推理到货/厂验/安装/验收等
  完成时点，写入 .skill/schedule.json 的 critical_nodes；请款对齐用 window_end，
  对人默认报「月+上中下旬」。务必在用户提到进度计划、甘特、Schedule 基座、关键节点、
  到货/厂验/安装/验收倒排、请款完成时点、critical_nodes、请款时间线时使用。
  可单独使用；系统内与履约/建包同步见 skill-orchestration。
---

# 进度计划关键节点分析（Agent 主导）

**全局原则**：先理解再处理（见 `skill-orchestration`）。  
本 Skill 的主路径是 **Agent 读懂进度表 → 推理节点 → 落盘**；脚本只做校验、写文件、可选时间线。

## 编排硬规则（摘要）

跨 Skill / 进度 / 合同 PDF / 邮件分发 → 先读 `<skills-root>/skill-orchestration/ALWAYS.md`（细节见同目录 `README.md`）。
单独使用功能 Skill 时禁止擅自串联履约/请款；脚本已串完的不要双跑；时间线对人只有 `项目档案/00_进度计划/关键节点时间线.html` 一份。
`skills-root` = 本机 Skills 安装根（WorkBuddy 常见 `~/.workbuddy/skills/`）。命令写成 `python3 <skills-root>/<技能名>/scripts/…`。

## 权威文档

- `references/node-taxonomy.md` — 节点码表与包类型模板（Agent 推理时对齐 `node_code`）
- `references/matching-rules.md` — **Agent 推理规则**（归属、explicit/inferred、倒排思路、冲突）；关键词表仅作弱提示
- `references/schedule-io.md` — **输出契约**（JSON / 摘要）
- `references/presentation.md` — 完成时点 / 旬粒度 / **时间线视觉与交互**（改 HTML 必读）
- `<skills-root>/mpp-to-excel/SKILL.md` — 收到 `.mpp` / Project XML 时必先调用
- 系统内多 Skill 协作 → `<skills-root>/skill-orchestration/README.md`

## 谁干什么

| 角色 | 职责 |
|------|------|
| **Agent** | 读源表与采购包清单；判断每行语义与包归属；按模板补全缺失关键节点；写清 `basis` / `confidence`；吃不准 → `pending` / `needs_confirm` |
| **脚本** | 校验字段与日期；**整盘或按包 merge** 写入 `.skill/schedule.json`；可选 Markdown 与**项目级**时间线 HTML；建包后脚本同步**只重渲**那一份 HTML |

可选脚本 `analyze_schedule.py`：仅在要**粗草稿**或无 Agent 时使用；产出须经 Agent 审过再当定稿。**禁止**用它整盘覆盖已有总包节点。

## 已定产品原则（必须遵守）

1. **主交付**：结构化数据（`.skill/schedule.json`）。需要可视化时用时间线 HTML，**视觉必须遵守** `presentation.md` §4（禁止糙默认模板）。
2. **完成时点语义**：关键节点回答「何时完成（可请款）」。机器可留 `window_start`/`window_end`，**对齐与口头汇报一律以 `window_end` 为准**。
3. **对人默认旬粒度**：`YYYY年M月上/中/下旬`；JSON 仍存 ISO 日。
4. **时间线只有一份给人看**：`项目档案/00_进度计划/关键节点时间线.html`（另写 `.skill/critical_nodes_timeline.html` 同内容）。**禁止**再写采购包目录下的时间线 HTML。
5. **进度入口**：先认附件格式再转换；`.mpp`/XML 经 `mpp-to-excel` → CSV；已是机读 csv/xlsx 可直接进本 Skill。人看版 `*_project_view.xlsx` 按下面输入表处理。
6. **低置信须确认**：吃不准就 `pending` / `needs_confirm`，不静默当定稿。
7. **不准用字典冒充理解**：任务名各异；用上下文推理，关键词表最多当联想，不能当唯一判决。
8. **总包 ≠ 抽象项目级**：公共节点 `package_name=总包`（新写入禁止 `_project`；旧数据可读）。各采购包只挂请款相关节点。包级「验收」默认对齐总包/客户验收前后。

## 能力边界

- **做**：理解进度表 → 归属采购包 → 匹配/推断关键节点 → 结构化契约 + 可选摘要/时间线（时间线视觉见 `presentation.md`）
- **不做**：另做履约看板产品；不写合同付款比例；不渲染履约卡片
- **定位**：可单独使用；系统内何时同步卡片/建包见编排 Rule（说明书）

## 输入（先认格式，再进本 Skill）

**不是「只能读 CSV」，也不是「默认一定是 MPP」。**  
正确顺序：**先判断附件是哪种进度** → 需要时转成机读表 → 再推理关键节点。

| 认出来的格式 | 怎么处理 |
|------|------|
| 已是机读任务表（`.csv` / 扁平 `.xlsx`，第 1 行是「任务名称/开始/结束…」） | **直接**给本 Skill 读 |
| `.mpp` / Project XML | 先跑 `mpp-to-excel` → 得到 `*_schedule.csv`，再用 CSV |
| 普通粗表 Excel（有任务名+日期列，但不是本仓库产出的甘特壳） | 可先走 `mpp-to-excel` 规范化成 CSV，或 Agent 直接读 xlsx |
| **人看版** `*_project_view.xlsx`（第 1 行像「项目:…」，右侧是甘特色块） | **不是源表**。优先找同目录 `*_schedule.csv`；没有则回到原始 `.mpp`/任务表，**禁止**把 project_view 当源硬转 |

最低列（机读表）：任务/里程碑名称、开始、结束；可选采购包/专业。  
表头约定见 `<skills-root>/project-foundation/references/schedule-csv-schema.md`。

采购包清单：Tracker CSV，或对话/JSON 中的包名+类型。

## 输出

唯一真源：`{project_root}/.skill/schedule.json`（`milestones` + `critical_nodes` + `pending`）。  
本 Skill 的 pending **只写这份**；禁止写入项目 `.skill/pending.json`（脚本会硬拦）。

可选：`.skill/critical_nodes.md`；时间线见上「只有一份」。

字段语义见 `references/schedule-io.md`。`source`：`explicit` | `inferred` | `aligned` | `manual`。

## 工作流（Agent 主路径 · 必须遵守）

1. 确认项目根；收集进度附件与采购包列表（含 `package_type`）
2. **先认进度格式**（见上表）：该转 CSV 的先转，确认手里是机读任务表
3. 若源是 `.mpp` / Project XML（或需规范化的粗表）：先执行 `mpp-to-excel`，再用 `*_schedule.csv`
4. **阅读**进度表全文（或足够上下文）：搞清总包锚点、各包粗条/细节点、中英混写含义——**先理解**
5. 阅读 `node-taxonomy.md`、`matching-rules.md`、`presentation.md`（若尚未加载）
6. **推理**并整理 `critical_nodes` + `pending`（按包类型模板；完成时点用 `window_end`；依据写进 `basis`；公共节点挂「总包」）
7. **落盘**：调用 `write_critical_nodes.py`（校验 + 写入；可选 `--write-md` / `--write-timeline`）
8. 汇报：节点数、`inferred` 数、`pending`；对人日期用旬；强调**完成时点**
9. 汇报完即停。系统内后续见编排说明书

### 标准命令（整盘落盘）

```bash
python3 <skills-root>/critical-nodes/scripts/write_critical_nodes.py \
  --project-root "/path/to/project" \
  --nodes-json "/path/to/critical_nodes_draft.json" \
  --source "项目档案/00_进度计划/project_schedule.csv" \
  --write-md \
  --write-timeline
```

### 系统内：刚建了采购包 XXX（只 merge 这个包）

接到「刚建了包 XXX」时（编排层会点到本 Skill）：

1. **读**进度表 + 该包类型 / 邮件交期等上下文  
2. **只推这个包**的关键节点（不要重算整盘、不要动总包行，除非用户明确要改总包）  
3. **merge 写入**（保留已有总包与其它包）：

```bash
python3 <skills-root>/critical-nodes/scripts/write_critical_nodes.py \
  --project-root "/path/to/project" \
  --nodes-json "/path/to/only_XXX_nodes.json" \
  --merge-package "XXX" \
  --write-timeline
```

4. 重渲后的 HTML 仍是**项目那一份**：总包行还在，下面多一行 XXX

人话：PM 打开  
`项目档案/00_进度计划/关键节点时间线.html`  
——上面仍是总包节点，新建的采购包会多出一行。

### PM 在时间线上改完之后（本地 HTML）

1. 双击打开 `项目档案/00_进度计划/关键节点时间线.html`  
2. 点「编辑」→ 可连续改多个包（标「有未保存的修改」即可，不必每改一次就存）  
3. 全部改完点一次「保存全部修改」→ 覆盖该 HTML + 把 `schedule.json` 放进 `.skill/`  
4. 下次仍打开**同一个** HTML 文件

### 建包后脚本只重渲（不发明节点）

`sync_schedule_timeline.py`：已有 `critical_nodes` 时**只重渲**项目时间线（+ `.skill` 副本），不重跑字典、不写包目录。

```bash
python3 <skills-root>/critical-nodes/scripts/sync_schedule_timeline.py \
  --project-root "/path/to/project" \
  --package-name "BMS"
```

（`--package-dir` 若传入会被忽略，仅为兼容旧调用。）

无节点时：应走上面的 Agent merge；仅显式 `--draft-analyze` 才出待审草稿。

### 可选：自动草稿（非主路径）

```bash
python3 <skills-root>/critical-nodes/scripts/analyze_schedule.py \
  --project-root "/path/to/project" \
  --source "…/project_schedule.csv" \
  --write-md
```

输出仅作草稿；Agent 必须审改后再经 `write_critical_nodes.py` 定稿（建包追加用 `--merge-package`）。

## 样例

- `samples/explicit/` — 计划已写明到货/安装（供 Agent 练习与草稿对照）
- `samples/coarse/` — 仅有专业粗条，需推理
- `evals/evals.json` — 评测提示（验收以 Agent 理解 + 契约为准）
