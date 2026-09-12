# Agent 推理规则（归属 · 显式/推断 · 倒排 · 冲突）

本文件给 **Agent** 用，不是给关键词引擎当唯一判决。  
改规则先改本文档；脚本只校验契约与落盘，不替代理解。

## 0. 总原则

1. **先读懂再归类**：同一件事可能叫「到货 / 到场 / material delivery / 材料进场」。看整行与上下文，不要只靠子串。
2. **`node_code` 必须落在** `node-taxonomy.md` 码表内；展示名可中英，码不能自造。
3. **完成时点** = `window_end`（请款、排序、时间线、口头汇报）。`window_start` 仅表示作业跨度（可选）。
4. **吃不准** → `pending` 或 `needs_confirm: true`，并写清要问 PM 什么。

## 1. 任务 ↔ 采购包归属（优先级）

1. 进度表「采购包 / 专业」列非空 → 直接归属该包  
2. 任务名明显含包名或其别名  
3. 仍无归属且明显是总包公共节点（许可证、隐蔽、竣工/移交等）→ 归 **总包**
4. 否则 → `pending`（`unmapped_task`），不要硬塞

（兼容：旧稿若写 `_project`，新分析应改为 `package_name=总包`。）

## 2. explicit / inferred / aligned

| source | 何时用 |
|--------|--------|
| `explicit` | 原计划已有可对应到该 `node_code` 的行（名称或上下文能对上），窗口取该行开始/结束 |
| `inferred` | 模板必推节点在原计划没有对应行，但有粗条或项目锚点可合理倒推 |
| `aligned` | 用邻近已识别节点对齐得到（例：进场对齐到货完成日；验收对齐客户验收） |
| `manual` | PM 在时间线 HTML 拖动/新增/删除后经 `apply_timeline_edits` 落盘 |

`manual` **优先保留**：除非用户明确要求「整表重算关键节点」，Agent 不要用推断覆盖已有 `manual` 节点。

`confidence` 建议（可按把握微调）：

- 原文明确 + 包归属清楚：`0.9`–`0.95`
- 原文明确但包靠猜：`0.7`–`0.8`
- 粗条倒推、依据充分：`0.65`–`0.75`
- 仅靠项目级锚点硬估：`≤0.5` → 通常 `pending` 或 `needs_confirm`

### `basis` 写法（对人 · 强制两段）

**不要**写「计划里缺什么」。只写：

1. **依据**：你看了进度表里的哪一行（任务原名 + 开始/结束日；可多行用分号）
2. **定法**：怎么从这些行定出当前 `window_end`

落盘可用单字段，用全角竖线分隔：

```text
依据：计划行「配电箱安装 …」开始 2026-09-17；下单「PAU/VRV/PDB」结束 2026-08-03｜定法：到货须不晚于安装开始，完成日取 2026-09-17
```

倒推/对齐节点默认视为待 PM 确认；PM 在时间线点「确认无误」后写 `pm_confirmed: true`，不再进待确认列表。

## 3. 粗条与倒排（inferred 思路）

**粗条**：任务名主要是包名/专业段（如 `BMS`、`幕墙施工`），没有到货/安装/验收等节点语义 → 作为该包工期锚点 `[S, E]`。

按包类型默认必推节点见 `node-taxonomy.md`。无原文时，可用下列**比例作起点**（允许按项目常识调整，但须在 `basis` 说明）：

### 供应

| node_code | 相对粗条 |
|-----------|----------|
| `delivery` | 整段 `[S, E]` 视为到货完成窗口；完成时点取 `E` |

### 供装

| node_code | 相对 `[S,E]`，`D=E-S` |
|-----------|----------------------|
| `delivery` | 约前 1/4 结束 |
| `site_access` | 紧接到货后 |
| `install_complete` | 约中后段结束 |
| `prelim_accept` / `final_accept` | 靠后；且不宜晚于项目移交 |

### 顾问

| node_code | 相对粗条 |
|-----------|----------|
| `concept` → `detail_deliverable` → `deliverable_accept` | 前 / 中 / 后 三段完成时点 |

无粗条时：不要瞎编精确日；优先 `pending`，或低置信 + `needs_confirm` 并标明依据。

### 3.1 包级「验收」对齐

无该包独立验收行时：验收完成时点默认跟总包/客户验收（如 Client final acceptance）前后对齐，**与项目验收日相差不宜超过约一个月**；禁止把「安装刚完成」直接当成验收请款完成日。

## 4. 冲突检查（写入 `risks[]` 或 pending）

同包内用 **`window_end`（完成日）** 按 taxonomy 顺序比较：

1. 后序节点完成日早于前序 → 风险  
2. `delivery` 完成晚于 `install_complete` 完成 → 风险  
3. 验收类完成晚于 `project_handover`（或竣工）→ 风险  
4. 缺开工或缺移交/竣工 → 项目级 `pending`

## 5. 关键词表（弱提示 · 非判决）

下列词汇**仅帮助联想** `node_code`。命中不等于定论；未命中也不等于不是该节点。  
真实计划里「BMS安装」「到场」「材料进场」等常见写法，必须靠语义判断。

| node_code | 常见说法（举例） |
|-----------|------------------|
| `project_start` | 开工, commencement, 进场动员（项目级） |
| `project_interface` | 界面, 交接, 结构移交, 精装进场 |
| `project_completion` | 竣工, practical completion, 完工 |
| `project_handover` | 移交, handover, 开业, soft opening |
| `po_confirm` | 下单, PO confirm, 签约下单 |
| `fat` | 厂验, FAT, ex-works |
| `shipment` | 发运, shipment, ETD/ETA（须确认是否真发运） |
| `delivery` | 到货, 到场, 材料进场/到场, delivery, arrival |
| `site_access` | 进场安装, site access, mobilization（别与「材料进场」混淆） |
| `install_complete` | 安装完成, 安装, 安装工程, installation |
| `commissioning` | 调试, commissioning, 联调 |
| `prelim_accept` | 初步验收, 初验, snagging |
| `final_accept` | 最终验收, 终验, taking over |
| `warranty_start` | 质保起算, DLP |
| `concept` | 方案, concept, schematic |
| `detail_deliverable` | 施工图, IFC, 成果交付 |
| `site_support` | 现场配合, 驻场 |
| `deliverable_accept` | 成果验收, 终稿验收 |

易混：

- 「材料进场 / 到场」→ 多属 **`delivery`**，不是 `site_access`
- 「进场动员」在项目总控语境 → 多属 **`project_start`**
- 裸「进场」看前后文：安装班组进场 vs 材料进场

## 6. MPP

本 Skill **不直读** `.mpp`。先 `schedule-mpp-excel` → `*_schedule.csv`，再按上文推理。

## 7. 呈现

对人汇报旬粒度、时间线 HTML 等 → [`presentation.md`](presentation.md)。
