---
name: po-flow
description: >-
  合同履约结构化（Skill 1 · MVP · 从建包起）。履约邮件（RFP/技术确认/Raise PO/付款条件/合同）→
  归档 → Tracker → 干净 card-data → 调用 vendor-card 出界面。
  项目初始化归 Skill 0；请款入账归 Skill 2；变更归 Skill 3；进度勿手猜日期。
  务必在用户提到采购包、RFP/RFQ、Raise PO、履约卡片、Tracker、里程碑、付款条件（非请款申报）、pending、履约邮件时使用。
---

# 合同履约结构化（Skill 1）

一句话：**从建包起**，把履约邮件变成 Tracker + 包文件夹 + 干净 `card-data`，再交给履约卡片 Skill 出 HTML。做到哪为止，见下面的表。

## 编排硬规则（摘要）

跨 Skill / 进度 / 合同 PDF / 邮件分发 → 先读 `<skills-root>/skill-orchestration/ALWAYS.md`（细节见同目录 `README.md`）。
单独使用功能 Skill 时禁止擅自串联履约/请款；脚本已串完的不要双跑；时间线对人只有 `项目档案/00_进度计划/关键节点时间线.html` 一份。
`skills-root` = 本机 Skills 安装根（WorkBuddy 常见 `~/.workbuddy/skills/`）。命令写成 `python3 <skills-root>/<技能名>/scripts/…`。

## 做什么 / 不做什么

| 做 | 不做 |
|----|------|
| 处理 `fulfillment.*` 邮件（或粘贴） | 项目初始化 → Skill 0 |
| 建包 / 更新 Tracker / 归档 `.eml` | 请款申报入账 → Skill 2 |
| 写出/更新 `card-data.json`，调用 vendor-card | 变更 / Change PO → Skill 3 |
| 搞不定的字段进 `pending.json`，再问人 | 手写 HTML；手猜进度日期 |
| | 代写 RFP、代发 Raise PO |

前置：`.skill/project.json` 已存在（否则先 Skill 0）。

## 主路径

优先走脚本（邮件已在盘上时）：

```bash
python3 <skills-root>/po-flow/scripts/process_email.py \
  --eml "/path/to/mail.eml" \
  --project-root "/path/to/project" \
  --route-json "/path/to/route.json"   # mail-inbox 分发时带上
```

对话里改数据后刷界面（`process_email` 内部已含则不必再跑）：

```bash
python3 <skills-root>/vendor-card/scripts/render_card.py \
  --package-dir "/path/to/{序号}_{采购包}_{供应商}/" \
  --patch '{"supplier_name":"…", …}'
```

收信入口是项目根 **`待处理邮件/`**（`mail-inbox` 的 `process_drop_folder.py`）。本 Skill 只消费分过来的 `fulfillment.*`。误投初始化/变更时 `process_email` 只拒收挂 pending（兜底，**不是**第二套分类器；防误伤真源在 mail-inbox）。这版不要教用户连邮箱。

**线程回信**：分类器只认关键词、不懂「这是回信」。`Re:` 里引用的原 RFP 常被判成 `fulfillment.rfp` + `confidence: high`。**high 不等于对。** Agent 必须读正文**最新一段**，按 mail-inbox 意图表覆写 `intent`，route.json 加 `"intent_verified": true` 再跑 `process_email`。不要另造分类器，也不要跟着错判再建一次包。脚本兜底：已建包 + 回信主题 + 仍判成 RFP → pending `possible_thread_reply`，等你覆写。

## 硬规则（短）

1. **先理解再处理**（全局）：见 `skill-orchestration`「全局原则」。本 Skill：先搞清步骤与附件再写 Tracker / `card-data`；脚本抽不出则打开附件读懂或 `pending`。回信按上面「线程回信」办。
2. **归档**：归属某包的邮件 → 整封 `.eml` 进 `07_往来文件/`。`01_合同报价/` 只放报价/合同，禁止签名动图。图纸：有 dwg/pdf/zip 进 `02_图纸/`；签名/inline 图跳过；**只有 Box/SharePoint 等链接时必须在 `02_图纸/` 留指针文件**（URL+密码），不要留空文件夹让人以为没图纸。不要擅自登录云盘下载。
3. **金额（附件为准）**：Tracker 必须有「不含税 / 含税」。**报价附件 > 邮件正文**。冲突 → 写附件并 `pending`（`amount_mismatch_body_vs_quote`）；有附件抽不出 → `quote_amount_unparsed`；两侧不全 → `tax_rate_uncertain`。
4. **对接人**：To/Cc/From 里供应商域名都收，`; ` 拼接。
5. **里程碑**（有时间戳=完成）：RFP 发出 → 技术方案已确认 → 商务报价已确认 → PO 已发起 → 已结算。Raise PO 同时打「商务报价已确认 + PO 已发起」。
6. **付款节点**：任意履约邮件正文能解析就写入 `card-data`（中+英）；合同/报价 PDF 先走 `read-pdf` 读正文，再由本 Skill `extract_contract_pdf.py` 抽节点候选。
7. **界面**：只维护 `card-data` → 调 **vendor-card**（出卡片，并自动调 **payment-sheet** 刷请款申请页）。`process_email` / `render_card` 已成功且有 `claim_form_path`（或 `did` 含 `payment-sheet.sync`）时，**同一回合不要再手跑** `render_card` / `payment-sheet` sync（除非脚本失败要补）。
8. **进度（与编排对齐）**：
   - 见到 `.mpp` / 甘特 / Master Schedule → 按 `skill-orchestration` 表 B：`mpp-to-excel` → **Agent 主导** `critical-nodes` → 再渲染卡片；**禁止手猜日期**。
   - `add_package` / `process_email` 建包后，脚本**最多**重渲**项目级**时间线 HTML：`项目档案/00_进度计划/关键节点时间线.html`（有已有 `critical_nodes` 时只重渲、不覆盖节点；尚无节点则 skip）。**不会**给这个新包自动补「到货」等关键节点。
   - **RFP 建包成功后（同一回合）**：Agent 必须把包名、类型、邮件里的交期/到货日交给 `critical-nodes`（按编排表 B）**merge** 该包节点；**不要**手改 `schedule.json`；**不要**再手跑 `analyze_schedule` 覆盖总包/已有推理。
   - 对人汇报只指项目档案那一份时间线；**不要**把包文件夹里的 `关键节点时间线.html` 当成交付物介绍。
9. **口径只看本项目 + 这封邮件**。不要翻本机其它旧项目的 Tracker / 文件夹来猜类型、节点。旧表结构会过期，翻了也白干。

细则（表头、邮件样例、邮箱参数）：`references/` 与基建库 `project-foundation`（安装后与 Skill 并列的 `project-foundation`，不是 Skill）。

## 步骤（邮件 → 动作）

| 步骤 | 识别 | 主要动作 |
|------|------|----------|
| 1 RFP | RFP/RFQ | `add_package` / process_email：建包、`RFP 发出`、归档、可选付款节点、渲染 → **再**按表 B 把本包交给 critical-nodes merge |
| 2 技术确认 | 顾问确认技术（以**最新回复**为准，不是引用里的 RFP） | 归档图纸或云盘指针 → `技术方案已确认`（RFP 发出那栏不动）→ 更新 card-data；未闭环行动项对人说清 |
| 3 Raise PO | Raise PO | 归档报价 → 抽金额 → `PO 已发起` → 更新 card-data |
| 4 付款/合同 | 付款指示或合同 | read-pdf 读正文 → 本 Skill 解析节点 → card-data → 渲染；总包滚动款归 Skill 2 |
| 极简归档 | PO 后杂文件 | `archive_file.py` 进 03~06 |

误投初始化 / 变更 / 请款时，`process_email` 拒收并挂 pending，提示走 Skill 0 / 3 / 2。正常应由 mail-inbox 直接分对。

**步骤 2 收尾（脚本不会替你做完的两件事）**：

| 情况 | Agent 做什么 |
|------|----------------|
| 附件只有 inline 图，图纸在云盘链接里 | `process_email` 会尽量在 `02_图纸/` 写指针；若脚本没写到，自己补一份 `.md`（链接+密码+来源邮件）。对人说「图纸在云盘，文件夹里是指针」 |
| 顾问夹了 PM 待办（如报价前先去现场核实） | **不是**卡片字段，别硬塞八格。写入对人确认清单；若卡住下一步（报价 / Raise PO 之前必须做完）→ `pending.json`，`reason=open_action_item` |

## 产出

- Tracker：`.skill/status_tracker.csv` + 根目录 `{项目名}_Status Tracker.xlsx`
- 包目录：`{序号}_{采购包}_{供应商简称}/`（含 `01`…`09`，往来在 `07`；简称见 `scripts/supplier_naming.py`，约 ≤20 字整段保留）
- `card-data.json` → 经 vendor-card 得到 `履约条件卡片.html`；经 payment-sheet 得到 `请款申请.html`
- 进度：新包节点按上面第 8 条交给 critical-nodes merge
- `pending.json`：待确认项

包类型：供应 / 供装完整支持；顾问、总包占位。建包后要改类型：`update_tracker.py --action update --package-name … --package-type 供装`。打印出来的「采购包类型」必须已经是新值；还是旧值就当失败，不要只看「命令成功了」。

## 对人确认

先自动落盘，再问。示例：

```
【Skill1 · 待确认】项目 SAMPLE · 步骤1 · RFP
1. 采购包名称：BMS
2. 供应商：BOSCH Building Technologies
3. 对接人邮箱：procurement@bosch-build.example.com
4. 采购包类型：供应
回复：全部确认 / 2 供应商=xxx / 取消

【Skill1 · 待确认】项目 SAMPLE · 步骤2 · 技术确认
1. 采购包：BMS（已有包，未新建）
2. 分类器原判：fulfillment.rfp / high → 已覆写为 fulfillment.tech_confirm
3. Tracker：技术方案已确认 = 2026-09-15（RFP 发出未改）
4. 图纸：无 dwg/pdf；已在 02_图纸 留下云盘指针
5. 未闭环：报价前须现场核实安装位置（已记 pending，未写入卡片）
回复：全部确认 / 5 先不做 / 取消
```

## 相关 Skill（需要时再读）

| 需要时 | 去哪 |
|--------|------|
| 编排 / 禁止双跑 | `skill-orchestration` |
| 基建 / Tracker 表头 | `<skills-root>/project-foundation`（共用库，不是 Skill） |
| 出 HTML | `vendor-card` |
| 收信分发 | `mail-inbox` |
| 初始化 | `new-project` |
| 进度 | `mpp-to-excel` → `critical-nodes`（建包后 merge 本包节点） |
| 合同 / 报价 PDF | `read-pdf`（只读正文）→ 本 Skill 抽付款节点 |
| 请款 / 变更 | `payment-flow` / `change-flow` |

本目录：`references/email-templates.md`、`mailbox-setup.md`、`deps-ocr-pdf.md`。

## 演示

```bash
python3 <skills-root>/po-flow/scripts/run_e2e_demo.py
# → samples/Sample-Project/
```
