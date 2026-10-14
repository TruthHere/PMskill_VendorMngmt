# 进度计划编排（系统内强制调用链）

**服从**上级 [`../README.md`](../README.md)。  
凡出现进度计划（`.mpp` / Project XML / 甘特 / Master Schedule）且在**供应商履约系统内**处理时，禁止不读进度瞎猜日期。

> 用户只要「转 Excel」或「析关键节点」、未提履约/请款 → 走功能 Skill **单独使用**，不必跑到 vendor-card。时间线仍只写项目那一份，不要往采购包文件夹塞 HTML。

## 硬规则 · 对人只有一份时间线

对人看的活文档**只有**：

`项目档案/00_进度计划/关键节点时间线.html`

- **建项时生成**（`init_project` 之后同一回合 `render_timeline.py`；有进度则走下面 ①②，同样覆盖这一份）。
- **每建一个采购包、每补节点**：覆盖更新这一份。
- **禁止**再往采购包文件夹写 `关键节点时间线.html`。
- `.skill/critical_nodes_timeline.html` 可以继续作为机器副本，**不要**当给人看的第二份产品。

删掉旧说法「产出 2：`{采购包目录}/关键节点时间线.html`（该包过滤视图）」。那份不是产品。

## 强制链路（系统内 · 先认格式）

**不要默认「附件一定是 mpp」。** 先判断附件类型，再进转换/推理：

```text
进度附件
  → ⓪ 认格式
       ├─ 已是机读 csv / 扁平任务 xlsx → 直接 ②
       ├─ .mpp / Project XML / 需规范化的粗表
       │     → ① mpp-to-excel
       │          产出：*_schedule.csv（机读）
       │               + *_project_view.xlsx（给人看；禁止再当源）
       └─ 人看版 *_project_view.xlsx（假源）
             → 找同目录 *_schedule.csv；没有则回原始 mpp/任务表
               （禁止把 project_view 硬喂给转换脚本）
  → ② critical-nodes（Agent 主导）
       Agent 读懂表 → 按包推理 critical_nodes
       → write_critical_nodes.py --write-timeline 校验落盘
       → .skill/schedule.json
       → 对人：项目档案/00_进度计划/关键节点时间线.html（覆盖）
       → 机器副本：.skill/critical_nodes_timeline.html
  → ③ vendor-card
       读 schedule.json / critical_nodes
       → enrich 付款节点 schedule_window
       → render_card.py（履约卡片 → 自动 payment-sheet 刷请款页）
```

已是机读任务表时：跳过 ①，从 ② 开始。

`analyze_schedule.py` 字典草稿**不是**本链路的默认步骤。建包后更**禁止**拿它整盘重算来覆盖总包节点。

## 采购包录入时（表 A 脚本 + 表 B Agent · 同一回合）

每录入一个采购包（`add_package` / RFP）分两截，**都要做**，不要把第二截推给洗衣机。

### 表 A · 脚本 `sync_schedule_timeline.py`

入口（与 `critical-nodes` 的 SKILL.md 一致；`--package-dir` 可省略，写了也会被忽略）：

```bash
python3 .cursor/skills/critical-nodes/scripts/sync_schedule_timeline.py \
  --project-root "/path/to/project" \
  --package-name "BMS"
```

行为：

- **只重渲** `项目档案/00_进度计划/关键节点时间线.html`（可顺带机器副本）。
- **不**覆盖已有 `critical_nodes`。
- **不**写包内 HTML。
- **不**给新包编到货/安装/验收节点。
- 尚无节点 → `skipped: no_critical_nodes`（这不是「脚本会补」，而是提醒走下面 Agent 主路径）。
- 无进度源时软跳过，不阻断建包。

### 表 B · Agent `critical-nodes`（建包成功后同一回合必须）

脚本不会自动补包级节点。**禁止**对用户说「脚本会自动补包级节点」。

同一回合必须：

1. Read `critical-nodes` SKILL.md。
2. **只为这个新包**追加到货/安装/验收等节点（merge）。
3. **不准把总包节点抹掉**（也不准把别的已有包节点抹掉）。落盘用现有命令：`--nodes-json` 里带上已有总包及其他包节点 + 本包新节点，再跑 `write_critical_nodes.py`（脚本按你交的整表写入，Agent 负责 merge）。
4. RFP/邮件里有明确到货日就写；没有就进度 `pending`（写 `.skill/schedule.json`，不要写项目 `pending.json`）。
5. 带 `--write-timeline`，覆盖更新项目那一份 HTML。

```bash
python3 .cursor/skills/critical-nodes/scripts/write_critical_nodes.py \
  --project-root "/path/to/project" \
  --nodes-json "/path/to/merged_nodes.json" \
  --write-timeline
```

`merged_nodes.json` = 已有节点（尤其总包）+ 本包新节点。不要只交本包。

**禁止**用 `analyze_schedule.py` 整盘重算来覆盖总包节点。

## Agent 必读 Skill

| 顺序 | 路径 | 职责 |
|------|------|------|
| ① | `.cursor/skills/mpp-to-excel/SKILL.md` | MPP→CSV/甘特 Excel |
| ② | `.cursor/skills/critical-nodes/SKILL.md` | **理解**进度 → 采购包×关键节点 → `write_critical_nodes`；建包后只 merge 本包 |
| ③ | `.cursor/skills/vendor-card/SKILL.md` → `payment-sheet` | 卡片；自动刷请款页 |

建项后若还没有时间线 HTML，先：

```bash
python3 .cursor/skills/critical-nodes/scripts/render_timeline.py \
  --project-root "/path/to/project"
```

只写项目那一份（+ 机器副本）。不要加「写到采购包目录」的用法。

## 禁止事项

- ❌ 因「本机没有 Java」放弃 MPP（应走 mppjs 或另存 XML）
- ❌ 只把 `.mpp` 归档却不调用 ①②（系统内）
- ❌ 不读进度表就编造完成日写入 `schedule.json`
- ❌ 把 `analyze_schedule` 关键词草稿直接当定稿
- ❌ 建包后用 `analyze_schedule` 整盘重算覆盖总包节点
- ❌ 建包后说「脚本会自动补包级节点」就收工
- ❌ 往 `{采购包目录}/关键节点时间线.html` 再写一份（该包过滤视图已废）
- ❌ 跳过 `critical-nodes` 直接把粗 CSV 当请款完成时点
- ❌ 把进度 `pending` 写进项目 `.skill/pending.json`（进度待确认只留在 `schedule.json`；脚本会硬拦）
- ❌ 业务回合拆 Skill 脚本翻实现、当场改 Skill 修小毛病（记 bug 另开任务；入口以各 SKILL.md 为准）

## 与付款节点的关系

- 合同/邮件决定 **付款节点名称与比例**
- `critical_nodes` 决定 **计划完成时点**（优先 `window_end`）
- 二者在 **vendor-card** 对齐；没有 schedule 基座时不要假装已对齐
