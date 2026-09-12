---
name: contract-fulfillment-struct
description: >-
  合同履约结构化（Skill 1 · MVP · 从建包起）。履约邮件（RFP/技术确认/Raise PO/付款条件/合同）→
  归档 → Tracker → 干净 card-data → 调用 fulfillment-card 出界面。
  项目初始化归 Skill 0；请款入账归 Skill 2；变更归 Skill 3；进度勿手猜日期。
  务必在用户提到采购包、RFP/RFQ、Raise PO、履约卡片、Tracker、里程碑、付款条件（非请款申报）、pending、履约邮件时使用。
---

# 合同履约结构化（Skill 1）

一句话：**从建包起**，把履约邮件变成 Tracker + 包文件夹 + 干净 `card-data`，再交给履约卡片 Skill 出 HTML。  
本 Skill **不画卡片、不办初始化、不办请款入账、不办变更**。

## 做什么 / 不做什么

| 做 | 不做 |
|----|------|
| 处理 `fulfillment.*` 邮件（或粘贴） | 项目初始化 → Skill 0 |
| 建包 / 更新 Tracker / 归档 `.eml` | 请款申报入账 → Skill 2 |
| 写出/更新 `card-data.json`，调用 fulfillment-card | 变更 / Change PO → Skill 3 |
| 搞不定的字段进 `pending.json`，再问人 | 手写 HTML；手猜进度日期 |
| | 代写 RFP、代发 Raise PO |

前置：`.skill/project.json` 已存在（否则先 Skill 0）。

## 主路径

优先走脚本（邮件已在盘上时）：

```bash
python3 .cursor/skills/contract-fulfillment-struct/scripts/process_email.py \
  --eml "/path/to/mail.eml" \
  --project-root "/path/to/project" \
  --route-json "/path/to/route.json"   # mail-inbox 分发时带上
```

对话里改数据后刷界面（`process_email` 内部已含则不必再跑）：

```bash
python3 .cursor/skills/fulfillment-card/scripts/render_card.py \
  --package-dir "/path/to/{序号}_{采购包}_{供应商}/" \
  --patch '{"supplier_name":"…", …}'
```

收信总入口是 **mail-inbox**（上线 WorkBuddy 每日两轮 `--once`；测试期终端按需）。本 Skill 只消费分过来的 `fulfillment.*`。误投初始化/变更时 `process_email` 只拒收挂 pending（兜底，**不是**第二套分类器；防误伤真源在 mail-inbox）。详见 `references/mailbox-setup.md`。

## 硬规则（短）

1. **先理解再处理**（全局）：见 `skill-orchestration`「全局原则」。本 Skill：先搞清步骤与附件再写 Tracker / `card-data`；脚本抽不出则打开附件读懂或 `pending`。
2. **归档**：归属某包的邮件 → 整封 `.eml` 进 `07_往来文件/`。`01_合同报价/` 只放报价/合同，禁止签名动图。
3. **金额（附件为准）**：Tracker 必须有「不含税 / 含税」。**报价附件 > 邮件正文**。冲突 → 写附件并 `pending`（`amount_mismatch_body_vs_quote`）；有附件抽不出 → `quote_amount_unparsed`；两侧不全 → `tax_rate_uncertain`。
4. **对接人**：To/Cc/From 里供应商域名都收，`; ` 拼接。
5. **里程碑**（有时间戳=完成）：RFP 发出 → 技术方案已确认 → 商务报价已确认 → PO 已发起 → 已结算。Raise PO 同时打「商务报价已确认 + PO 已发起」。
6. **付款节点**：任意履约邮件正文能解析就写入 `card-data`（中+英）；合同/报价 PDF 先走 `pdf-read` 读正文，再由本 Skill `extract_contract_pdf.py` 抽节点候选。
7. **界面**：只维护 `card-data` → 调 **fulfillment-card**（出卡片，并自动调 **payment-form** 刷请款申请页）。禁止手改 HTML；渲染后不要再单独刷请款页。
8. **进度**：见到 `.mpp` / 甘特 / Master Schedule → 按 `skill-orchestration` 跑 mpp-excel → critical-nodes → 再渲染；**禁止手猜日期**。建包时时间线脚本会默认同步，勿双跑。
9. **编排**：脚本已做完的事同一回合不要再手搓。总表见 `.cursor/skills/skill-orchestration/SKILL.md`。

细则（表头、邮件样例、邮箱参数）：`references/` 与基建库 `project-foundation`（`.cursor/lib/`，不是 Skill）。

## 步骤（邮件 → 动作）

| 步骤 | 识别 | 主要动作 |
|------|------|----------|
| 1 RFP | RFP/RFQ | `add_package` / process_email：建包、`RFP 发出`、归档、可选付款节点、渲染 |
| 2 技术确认 | 顾问确认技术 | 归档图纸 → `技术方案已确认` → 更新 card-data |
| 3 Raise PO | Raise PO | 归档报价 → 抽金额 → `PO 已发起` → 更新 card-data |
| 4 付款/合同 | 付款指示或合同 | pdf-read 读正文 → 本 Skill 解析节点 → card-data → 渲染；总包滚动款归 Skill 2 |
| 极简归档 | PO 后杂文件 | `archive_file.py` 进 03~06 |

误投初始化 / 变更 / 请款：不要当履约做完；`process_email` 拒收并提示走 Skill 0 / 3 / 2（兜底）。正常应由 mail-inbox 直接分对。

## 产出

- Tracker：`{项目名}_procurement_packages_status_tracker.csv` + xlsx  
- 包目录：`{序号}_{采购包}_{供应商}/`（含 `01`…`09`，往来在 `07`）  
- `card-data.json` → 经 fulfillment-card 得到 `履约条件卡片.html`；经 payment-form 得到 `请款申请.html`  
- 有进度源时：关键节点时间线（建包脚本默认同步）  
- `pending.json`：待确认项  

包类型：供应 / 供装完整支持；顾问、总包占位。

## 对人确认

先自动落盘，再问。测试期用 Cursor；上线用 WorkBuddy。示例：

```
【Skill1 · 待确认】项目 SAMPLE · 步骤1 · RFP
1. 采购包名称：BMS
2. 供应商：BOSCH Building Technologies
3. 对接人邮箱：procurement@bosch-build.example.com
4. 采购包类型：供应
回复：全部确认 / 2 供应商=xxx / 取消
```

## 相关 Skill（需要时再读）

| 需要时 | 去哪 |
|--------|------|
| 编排 / 禁止双跑 | `skill-orchestration` |
| 基建 / Tracker 表头 | `.cursor/lib/project-foundation`（共用库，不是 Skill） |
| 出 HTML | `fulfillment-card` |
| 收信分发 | `mail-inbox` |
| 初始化 | `project-init` |
| 进度 | `schedule-mpp-excel` → `schedule-critical-nodes` |
| 合同 / 报价 PDF | `pdf-read`（只读正文）→ 本 Skill 抽付款节点 |
| 请款 / 变更 | `payment-request` / `change-archive` |

本目录：`references/email-templates.md`、`mailbox-setup.md`、`deps-ocr-pdf.md`。

## 演示

```bash
python3 .cursor/skills/contract-fulfillment-struct/scripts/run_e2e_demo.py
# → samples/Sample-Project/
```
