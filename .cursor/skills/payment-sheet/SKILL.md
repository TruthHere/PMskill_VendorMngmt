---
name: payment-sheet
description: >-
  辅助 Skill：请款申请页与客户请款单 Excel。换项目/换业主时，根据客户既有请款单模板
  生成对应填写页（认模板 → 对照格子 → 刷请款申请.html）；页内一键下载版式一比一的 xlsx。
  读 card-data 与台账合同不含税额。不估算本次请款金额、不入账、不改 Tracker、不渲染履约卡片。
  被 vendor-card（渲卡片后自动刷页）调用。网页不展示已请。
  务必在用户提到请款申请页、payment form、payment-sheet、客户请款单模板、生成填写表单、
  换业主换模板、下载请款单 Excel、精调请款表单/请款申请 HTML 时使用。
---

# 请款申请页（payment-sheet · 辅助 Skill）

**全局原则**：先理解再处理（见 `skill-orchestration`）——只消费上游已写入的 `card-data` 与台账请款章节，不臆造金额。

**这张 Skill 干什么：** 用客户原来那张请款单。认模板时清空「要人填」的格子（样例项目名、金额等），下载时把本包信息写进这些格子。图、表头、换行、合并格全部留着。**不是重做一张表。**

请款金额默认不含税；**若客户模板写的是含税，填写页按含税提示，下载也按含税写。** 本次请多少由供应商自己填；本 Skill **不按比例代算**。

合同额从台账「金额不含税」带出。

## 编排硬规则（摘要）

跨 Skill / 进度 / 合同 PDF / 邮件分发 → 先读 `<skills-root>/skill-orchestration/ALWAYS.md`（细节见同目录 `README.md`）。
单独使用功能 Skill 时禁止擅自串联履约/请款；脚本已串完的不要双跑；时间线对人只有 `项目档案/00_进度计划/关键节点时间线.html` 一份。
`skills-root` = 本机 Skills 安装根（WorkBuddy 常见 `~/.workbuddy/skills/`）。命令写成 `python3 <skills-root>/<技能名>/scripts/…`。

## 两步（不要跳）

| 步 | 何时 | 做什么 |
|----|------|--------|
| **0 · 认模板** | 新项目、换业主、用户扔来客户标准请款单 | 体检 Excel → 起草对照表 → **用人话跟用户对一遍** → 写入项目 `.skill/payment-sheet/` |
| **1 · 刷填写页** | 认完模板之后；或渲履约卡片之后 | `sync_claim_form.py` 写出包内 `请款申请.html`，下载即填客户那张表 |

没有做过步骤 0 的项目，**请款单生成未启用**（填写页是空的提醒页）。不要拿技能里任何自带样例充数。只有用户把**本项目**客户请款单交来认过，才启用。

## 往原表里填（必须遵守）

| 要 | 不要 |
|----|------|
| 客户原件当底稿：清空要填的格子，再写入本包信息 | 照着样子**新做**一张 Excel |
| 图片、表头、自动换行、合并格、列宽行高原样留下 | 整表重写（图会丢、长字会被切掉） |
| 客户给 `.xlsx`：原样复制进项目再填 | 收 `.xls` / Word 并转换或重画 |

**目前只收 `.xlsx`。** 客户给老格式 `.xls` 或 Word（`.doc` / `.docx`）：停下来提醒「请款单模板目前只收 Excel 工作簿（.xlsx）。」请款单生成仍未启用。不要另存，也不要让使用的人先装软件。

步骤 0 细则：`references/template-profile.md`。

## 定位

| 做 | 不做 |
|----|------|
| 客户请款单 `.xlsx` → 项目对照表 + 填写页 | 渲染 `履约条件卡片.html`（归 `vendor-card`） |
| `card-data` + 台账 → `请款申请.html` | 请款提醒 / 入账 / 回写 Tracker（归 Skill 2） |
| 页内按钮 → 往**原来的**客户模板里填字（清空要填处 → 写入） | 从邮件抽付款条件（归 Skill 1）；用历史填表锁定 PO / 联系人 |
| 写入包内 `.claim-assets/` | 写 Change Log；把填表底稿当财务入账；手改包内 `请款申请.html`（改 `assets/claim-form.html` 后重跑）；把出 Excel 的做法写进 Skill 2 或 vendor-card |

## 已请口径（网页不展示，Excel 要带上）

下载 Excel 时：既往请款优先用 Tracker「已请金额」合成一行。

往哪一格写、要不要插既往行：**只看该项目** `.skill/payment-sheet/template-profile.json`。不要按业主品牌猜格子，不要套别的项目的对照表。

## 与相邻 Skill

| 谁 | 关系 |
|----|------|
| **Skill 0** | 对话建项时若用户给了 **`.xlsx` 请款单**：同一回合做步骤 0（只认模板，不 sync）。没给，或给了 `.xls` / Word：提醒未启用（后者加一句目前只收 `.xlsx`） |
| **Skill 1** | 写干净 `card-data` → 调 `vendor-card`；卡片渲染会**自动**刷请款页（步骤 1，用已认模板） |
| **vendor-card** | 渲完后调用本 Skill（`did` 含 `payment-sheet.sync`） |
| **Skill 2** | 客户批复后回写台账；消费本 Skill 产出的页 / Excel |
| **本 Skill** | 认模板、填写页、填客户 Excel |

系统内刚跑过 `render_card` 且已有 `claim_form_path` → **不要**再手跑步骤 1。认模板（步骤 0）**不**在 `init_project` / `render_card` 的脚本链上：建项时用户给了文件，Agent 按表 B **同一回合**自己跑。

## 权威文档

- `references/template-profile.md` — **认模板**（换客户必读）
- `assets/claim-form.html` — 填写页 HTML 真源
- `assets/fill-xlsx.js` + `assets/fill-insert-xlsx.js` + `jszip.min.js` — 页内按 ZIP 填格子（只改值，不重画）
- `references/claim-form.md` — 填写页行为与金额口径（格子以项目对照表为准）
- `scripts/inspect_payment_template.py` / `adopt_payment_template.py` — 步骤 0（只收 `.xlsx`）
- `scripts/sync_claim_form.py` — 步骤 1
- `scripts/fill_payment_application.py` / `patch_xlsx.py` — CLI 填表（ZIP 补丁）

## 标准命令

认模板（步骤 0）：

```bash
python3 <skills-root>/payment-sheet/scripts/adopt_payment_template.py \
  --xlsx "/path/to/客户请款单.xlsx" \
  --project-root "/path/to/项目根" \
  --title "客户名 请款单"
```

只刷请款页（步骤 1）：

```bash
python3 <skills-root>/payment-sheet/scripts/sync_claim_form.py \
  --package-dir "/path/to/{序号}_{采购包}_{供应商}/"
```

CLI 出 Excel（只出文件，不入账）：

```bash
python3 <skills-root>/payment-sheet/scripts/generate_payment_application.py \
  --response "/path/to/claim_response.json" \
  --package-dir "/path/to/01_xxx_Vendor" \
  --out-dir "/path/to/output"
```

## 输出

| 产物 | 说明 |
|------|------|
| `{项目}/.skill/payment-sheet/template.xlsx` + `template-profile.json` | 该项目用的客户模板和对照表 |
| `请款申请.html` | 同包可打开填表；主按钮下载客户请款单 Excel |
| `.claim-assets/` | JSZip + 填表脚本 + 模板副本 |
| CLI `.xlsx` | 填好的请款单（不是财务底稿） |
