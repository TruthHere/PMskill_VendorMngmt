# Skill 编排（项目级 Rule 配套长文 · 唯一真源）

> **这不是 Skill。** 不跑脚本、不收邮件、不出表。它是给 Agent 看的「谁先谁后」交通规则。  
> **短规则真源**：同目录 `ALWAYS.md`。Cursor 仓库对齐 `.cursor/rules/skill-orchestration.mdc`；WorkBuddy/CodeBuddy **项目**在建项时写入 `{项目根}/.codebuddy/rules/pm-skill-orchestration/RULE.mdc`（**不要**写用户全局 rules）。细节以本文为准。

**固定工序靠脚本串；需要理解/判断才交给 Agent。**  
其它文档若与本文冲突，**以本文为准**。

## 全局原则 · 先理解再处理

适用于本仓库**整套供应商管理能力**（Skill 0/1/2/3、现金流、mail-inbox、履约卡片、进度、PDF 等），不单属某一业务 Skill。

| 要 | 不要 |
|----|------|
| 先搞清：来件/文件在办哪一步、附件是什么、关键数字与结论在哪 | 只拿表头/关键词去套旧正则就当结论 |
| 回信只看**最新一段**在办哪一步（`Re:` 里引用的原 RFP/COD 不算本封意图） | 分类器 `confidence: high` 就当真；被引用原文带着跑 |
| 格式因项目而异仍靠**上下文**读懂（人能读清的，Agent 也应读清） | 因「没见过这种表头」就放弃附件、改信正文抄数 |
| 脚本抽不出 / 吃不准 → **打开原文理解**再写，或 `pending` 问人 | 静默用次优来源落库且不提醒 |

**权威来源**：能证明结论的原始附件优先于邮件摘录/转发转述（例如报价金额以报价文件为准；与正文冲突则写附件并提醒）。  
各业务 Skill 的细则（金额 pending 码、变更不定价等）写在各自 `SKILL.md`，不得与本原则相反。

## 两种用法（先分清）

| 模式 | 何时 | Agent 怎么做 |
|------|------|----------------|
| **单独使用** | 用户只要一项能力（转 MPP、析关键节点、读 PDF），不谈建包/请款/变更 | **只 Read 对应功能 Skill**；不要拉履约/Tracker/卡片 |
| **系统内协作** | 供应商履约整套（Skill 0/1/2/3、邮件、卡片、请款、变更） | 按下文表 A / 表 B 编排；功能 Skill 只当能力块被调用 |

### 可单独拎出的功能 Skill（本轮）

| Skill | 单独使用时只做 | 系统内额外挂钩（见下文） |
|-------|----------------|--------------------------|
| `mpp-to-excel` | `.mpp`/XML/粗表 → Project 视图 Excel + 机读 CSV | 归档到 `00_进度计划/`；交给 critical-nodes |
| `critical-nodes` | **Agent**读懂进度 → 推理关键节点 → `write_critical_nodes` 落盘（覆盖更新项目那一份时间线） | 建包后：脚本 sync **只重渲**那一份 HTML；**同一回合 Agent 必须**只给新包 merge 节点（见硬规则） |
| `read-pdf` | PDF → 统一 JSON/Markdown（只读正文，不抽付款节点） | Skill 1 步骤 4a 先读正文；付款节点由 Skill 1 抽取后写入卡片/Tracker |
| `payment-sheet` | 认客户请款单模板 → 出填写页；刷请款申请页 / 出 Excel（不入账）。**项目没有模板则未启用，禁止用技能自带样例或别的项目的表充数** | **Skill 0 建项时若用户给了请款单**：同一回合步骤 0 认模板（尚无采购包则不 sync）。没给模板：提醒未启用。渲卡片后由 vendor-card **自动刷页**（步骤 1；无模板则写未启用页） |
| `cashflow` | **只读**聚合 Tracker / schedule / 变更 → 按月出账预测 | 用户要看现金流时重算；**不写**履约/请款/变更 |

单独使用时：**禁止**因为「系统里还要刷卡片/请款」而擅自改履约数据。

---

## 人话版（系统内）

| 情况 | 谁负责「下一步」 | 大模型要不要参与编排 |
|------|------------------|----------------------|
| 收邮件、建包、改完卡片刷新请款页 | **脚本**按写死顺序做完 | 不要（编排层）。回信和看不准的仍要 Agent 读完再问 |
| 用户扔来 MPP / 合同 PDF / **客户请款单模板**；字段吃不准要问人 | **Agent** Read 功能 Skill 再跑 | 要 |

「请款同步」= 改完 `card-data` 并调用 **vendor-card** `render_card.py` 后，脚本会再调 **payment-sheet**，同包 `请款申请.html` 已**一并刷新**。Skill 1 / Skill 2 **不要**再单独刷请款页（除非只要刷页、不改卡片）。

---

## 目标架构（系统内 · 冻结）

### 定版原则

0. **先理解再处理**（上文全局原则）：先读懂来件与附件，再分类/落库/推进状态。
1. **唯一收信入口**：项目根 `待处理邮件/` 里的整封 `.eml`，或 Outlook 另存的 `.msg`（先转成 `.eml` 再分类），由 `mail-inbox/scripts/process_drop_folder.py` 扫描后再分类分发。不要把 IMAP / 企微轮询当这版步骤。
2. **唯一分类**：只 `mail-inbox/scripts/classify_mail.py`。
3. **唯一分发**：只 `mail-inbox/scripts/dispatch_mail.py` → Skill 0/1/2/3 handlers。
4. **Skill 1 只做履约**：建包起；只消费 `fulfillment.*`。
5. **功能 Skill 不写业务流程**：MPP/节点/PDF 的「在系统里谁先谁后」只写在本文，不写回三个功能 Skill 正文。

### 理想调用链（邮件）

```text
待处理邮件/*.eml 或 *.msg（.msg 先转成 .eml）
  → process_drop_folder.py（mail-inbox）
       ├─ fulfillment.*       → Skill 1（po-flow）
       ├─ payment_claim.*     → Skill 2（按五步推进请款；仅客户批复占用节点）
       ├─ change.*            → Skill 3（change-flow）
       ├─ 回信 / 低置信       → 留在待处理里，对话问人（回信须读最新一段后再 dispatch）
       └─ 像新建项目          → 留在待处理里，不在这个夹里建项
```

---

## 总原则

1. **先理解再处理**（全局，见上）：理解先于落库与编排动作。
2. **一条入口一种编排**：脚本已串完的下游，Agent **同一回合禁止再手搓一遍**。**例外**：建包后 `sync_schedule_timeline` 只重渲 HTML，**不算**已补包级节点；同一回合仍须走表 B merge。
3. **看输出再决定**：入口脚本若返回 `did: [...]` / `claim_form_path`，视为已完成对应步骤。`schedule_timeline` 只表示项目那一份 HTML 已重渲，**不是**新包节点已经补上。
4. **需要判断的一次性任务**：Agent 必须 Read 对应功能 Skill，禁止在业务 Skill 里手猜（尤其日期、付款节点）。
5. **单独 vs 系统**：触发词只命中功能能力、且用户未提履约/请款/变更 → 走「单独使用」；否则走系统内表 A/B。
6. **业务回合不拆脚本**：只跑各 `SKILL.md` 写明的入口命令。禁止翻 Skill 脚本改实现、禁止为修小毛病当场改 Skill。发现脚本 bug → 记下来另开任务，本回合继续用现有入口把业务办完。

---

## 关键节点时间线（硬规则 · 对人只有一份）

对人看的活文档**只有这一份**：

`项目档案/00_进度计划/关键节点时间线.html`

| 要 | 不要 |
|----|------|
| 建项时就生成这一份（`init_project` 立空项目后，同一回合用 `render_timeline.py` 写出空壳；有进度则走表 B 进度链路，同样覆盖这一份） | 等到建包才第一次想起时间线 |
| 每建一个采购包、每补节点：都是**覆盖更新这一份** | 再往采购包文件夹写一份 `关键节点时间线.html` |
| `.skill/critical_nodes_timeline.html` 可以当机器副本 | 把机器副本当给人看的第二份产品；对人报两条路径 |

**禁止**产出「`{采购包目录}/关键节点时间线.html`（该包过滤视图）」。包多一行，也是写进上面那一份，不是包文件夹里再塞一张。

---

## 表 A · 脚本编排（偏洗衣机）

入口脚本自己串下游；Agent 只处理结果 / pending，**不要重复调用「已自动」列**。

| 入口 | 脚本自动做什么 | Agent 还要做什么 | 禁止 |
|------|----------------|------------------|------|
| `process_drop_folder.py`（这版收件入口） | 扫项目根 `待处理邮件/`：`.msg` 先转成 `.eml`；高置信且不是回信的，分类并分发；已经归档的拿走原件；重复的跳过 | 把清单讲给用户。`needs_you` 的回信要读最新一段再 `dispatch_mail`，然后重跑本脚本收走原件。像建项的邮件不要在这夹里建项目 | 建「已处理邮件」；把 IMAP 轮询当这版入口；看不准仍改台账 |
| `mail-inbox` `dispatch_mail.py`（单封补处理） | classify → 按 `route_to` 调 Skill 1/2/3 | 只在读过正文、意图已经核对之后用。线程回信必须读最新一段再交 | 绕过待处理清单，对看不准的信直接改账 |
| `init_project.py`（Skill 0 对话建项） | 问齐必填后立空项目，并生成 `待处理邮件/`。**不**绑邮箱、**不**认请款单、**不**刷请款页、**不**用任何自带请款样例充数；**不**写时间线 HTML。已有 `.skill/project.json` 则拒绝覆盖 | 同一回合写出对人那一份 `项目档案/00_进度计划/关键节点时间线.html`（先 `render_timeline.py`；有进度再走表 B 进度链路覆盖）。用户**同时给了**客户请款单 `.xlsx` → **同一回合**表 B `payment-sheet` 步骤 0。没给，或给了 `.xls` / Word → **提醒未启用**（原话：还没有请款单模板，请款单生成尚未启用；非 `.xlsx` 再加一句目前只收 `.xlsx`） | 没问币种和是否含税就建；问邮箱/开票主体/分部号/对接人/顾问/面积；把认模板写进 `init_project`；没给文件却拿样例表充数；覆盖已有项目；建「已处理邮件」或空采购包；建项回合去 sync 尚不存在的采购包；对人报包内还有一张时间线 |
| `process_email.py`（经 dispatch） | 归档、更新 Tracker、调 vendor-card | 确认 pending | 逐步手调 render / 再 sync 请款页 |
| `update_tracker.py --action add-package` | → `critical-nodes/sync_schedule_timeline.py`：**只重渲** `项目档案/00_进度计划/关键节点时间线.html`（可顺带机器副本）。**不**覆盖已有 `critical_nodes`，**不**写包内 HTML，**不**给新包编节点 | **同一回合必须**交给 `critical-nodes`（表 B）：只为**这个新包**追加到货/安装/验收等（merge，不准把总包节点抹掉）。RFP/邮件有明确到货日就写；没有就 `pending`。然后覆盖更新那一份 HTML | 用 `analyze_schedule` 整盘重算覆盖总包节点；说「脚本会自动补包级节点」就收工；往采购包文件夹写 `关键节点时间线.html`；建包后再手跑一遍 sync |
| `vendor-card/render_card.py` | → 履约卡片 HTML → 自动调 **payment-sheet**（有模板则刷填写页；无模板则写「未启用」页） | 有 `payment-sheet.sync` 即完成刷页。有 `payment-sheet.disabled` → **必须转告用户**：还没有请款单模板，请款单生成尚未启用 | 渲染后再手跑 payment-sheet sync；无模板却拿样例表充数；为跨技能 import 拼 PYTHONPATH / 改 sys.path |
| `payment-sheet/sync_claim_form.py` | → 只刷请款申请.html（+ `.claim-assets`）；Variations 读 Change Log | 用户只要精调/重刷请款页时用 | 系统内刚跑过 render_card 已有 claim_form_path 时再手跑一遍 |
| Skill 3 `handle_change_email` | 只更新 Change Log + 归档 | 一般无需另操作 | 为变更去改采购包 Tracker / 写履约卡片 |

Skill 1 对话里改卡片：只调一次渲染：

```bash
python3 <skills-root>/vendor-card/scripts/render_card.py --package-dir "…" --patch '{…}'
```

---

## 表 B · Agent 编排（偏要动脑）

| 触发 | Agent 必须 | 禁止 |
|------|------------|------|
| `.mpp` / Project XML / Master Schedule / 甘特（**系统内**） | Read+执行 `mpp-to-excel` → **Agent 主导** `critical-nodes`（理解→推理→`write_critical_nodes --write-timeline`）→ 覆盖更新 `项目档案/00_进度计划/关键节点时间线.html` → 对各包 `vendor-card` render | 不读进度瞎填日期；只归档不解析；往采购包目录写时间线 HTML |
| 同上但用户**只要转 Excel / 只要关键节点**（单独使用） | 只跑对应功能 Skill，停在其输出；时间线仍只写项目那一份 | 擅自改卡片 / Tracker / 请款；写包内时间线 HTML |
| 已是合规 `*_schedule.csv`（系统内） | 可跳过 mpp-excel；仍须 critical-nodes（Agent）→ 覆盖项目那一份时间线 → 卡片 | 同上 |
| 新建采购包成功（`add_package` / RFP 建包） | 脚本 sync 已重渲项目时间线。**同一回合** Read `critical-nodes`：只给**这个新包**补到货/安装/验收。落盘用现有 `write_critical_nodes.py`（`--nodes-json` 必须带上已有**总包**及其他包节点 + 本包新节点，merge，不准抹掉总包；`--write-timeline` 覆盖项目那一份 HTML）。RFP/邮件里有明确到货日就写；没有就进度 `pending` | 用 `analyze_schedule` 整盘重算覆盖总包；只交本包节点把总包写丢；说「脚本会自动补包级节点」；往采购包目录写 `关键节点时间线.html`；拆脚本改 Skill |
| 合同 / 报价 PDF（Skill 1 步骤 4a） | Read+执行 `read-pdf` 读正文 → Skill 1 `extract_contract_pdf.py` 抽付款节点候选 → PM 确认后写卡片 | 绕过 read-pdf 全本渲图 / 自装 OCR；让 read-pdf 抽付款节点；用全局 pdf 伴侣读文字 |
| 用户只要读 PDF / OCR（单独使用） | 只跑 `read-pdf`；把 JSON/MD 交给用户 | 擅自写入履约卡片；改去用全局 pdf 伴侣读文字 |
| 用户明确说「重算关键节点 / 重刷时间线」 | 走 critical-nodes（Agent 重推理 + `write_critical_nodes --write-timeline`；或仅 `render_timeline.py` 重渲项目那一份）。**建包回合除外**：建包成功不是「强制重算」口令 | 改 Skill 1 冒充进度解析；用 `analyze_schedule` 字典草稿当定稿；建包后拿「重算」当借口整盘覆盖总包 |
| PM 在时间线改节点后保存 / apply | 写回 `schedule.json`、重渲 **项目那一份** 时间线（**不**默认刷履约卡片） | 只改 HTML 不落 `schedule.json`；用推断覆盖 `manual`；另存一份到采购包文件夹 |
| 字段置信不足 / 变更歧义 / 请款抽不出关键字段 | 写入或认领 **本 Skill 自己的** `pending`，问人 | 静默当定稿；关别人的 pending；把进度 pending 写进 `pending.json` |
| 用户说「处理待处理邮件」 | Read `mail-inbox`，只跑 `process_drop_folder.py`。把清单用白话讲完。`needs_you` 的回信读最新一段后再 `dispatch_mail`，然后重跑脚本收走原件 | 连邮箱；建已处理邮件；从这夹里建项；看不准就改台账 |
| Skill 0 **对话建项**且用户给了客户请款单 `.xlsx` | 先跑完 `init_project` → **同一回合** Read+执行 `payment-sheet` 步骤 0（inspect → 对照 → 用户确认 → adopt）。此时通常还没有采购包，**不要** sync 请款页 | 只口头说「下一步再认」就结束；没给文件却拿样例表充数；把认模板写进 Skill 0 脚本 |
| Skill 0 **对话建项**且用户**没给**请款单，或给了 `.xls` / Word | 建项照做；**必须提醒**：还没有请款单模板，请款单生成尚未启用。给了非 `.xlsx` 再加一句目前只收 `.xlsx`。不拿样例表充数、不转换 | 静默当已启用；用技能自带样例充数；把 `.xls` 重画成模板 |
| 客户标准请款单 / 换业主换模板 / 生成请款填写页（未在建项回合） | Read+执行 `payment-sheet` 步骤 0；**已有采购包**才 sync | 没对照就套别的项目/样例格子；把认模板写进 Skill 2 |

进度细节：`references/schedule-pipeline.md`（本目录）。  
PDF 细节：`references/pdf-pipeline.md`（本目录）。  
二者服从本文「谁编排」划分。

---

## 进度计划链路（系统内强制）

```text
.mpp / Project XML
  → ① mpp-to-excel
       → *_schedule.csv + *_project_view.xlsx
  → ② critical-nodes（**Agent 理解 + 推理** → write_critical_nodes --write-timeline）
       → .skill/schedule.json
       → 对人：项目档案/00_进度计划/关键节点时间线.html（唯一活文档，覆盖更新）
       → 机器副本：.skill/critical_nodes_timeline.html（不要对人当第二份）
  → ③ vendor-card/render_card.py
       → 履约卡片「计划时间区间」
       →（自动）payment-sheet → 请款申请页

新建采购包（表 A + 表 B，同一回合）
  → add_package
       → 脚本 sync_schedule_timeline：只重渲上面那一份 HTML（不覆盖节点、不写包内 HTML）
       → Agent critical-nodes：只 merge 本包节点（不准抹总包）→ 再覆盖那一份 HTML
```

已是 `.csv` / `.xlsx` 任务表：可跳过 ①，从 ② 开始。  
**禁止**在履约 Skill 内不读进度瞎猜日期。**禁止**说「脚本会自动补包级节点」。细则见 `references/schedule-pipeline.md`。

---

## 合同 PDF 链路（系统内 · 步骤 4a）

```text
合同 / 报价 PDF
  → read-pdf/scripts/read_pdf.py          # 只出正文 JSON/Markdown
  → Skill 1 extract_contract_pdf.py --read-json …
       → payment_nodes 候选（启发式）
  → PM 确认 → vendor-card / Tracker
```

**禁止**默认全本渲图。细则见 `references/pdf-pipeline.md`。

---

## 请款单模板链路（系统内 · 认模板 ≠ 刷页）

```text
对话新建项目（Skill 0 init_project）
  → 用户同时给了客户请款单 .xlsx
       → 同一回合 payment-sheet 步骤 0（认模板 → 项目 .skill/payment-sheet/）
  → 用户给了 .xls / Word，或没给模板
       → **不启用** payment-sheet（不拿样例表充数、不转换、不重画）。建项完成时必须提醒：
         「还没有请款单模板，请款单生成尚未启用。」
         若给了非 .xlsx：再加一句「请款单模板目前只收 Excel 工作簿（.xlsx）。」
       → 不阻塞建项

之后第一次建包并渲卡片（表 A）
  → vendor-card/render_card.py
       →（自动）payment-sheet 步骤 1
            ├─ 已认模板 → sync 请款申请.html
            └─ 未认模板 → 写出「未启用」页；did 含 payment-sheet.disabled；Agent 必须把提醒告诉用户
```

步骤 0 要看懂格子、跟用户对对照表，**不能**写进 `init_project.py`。  
步骤 1 刷页是洗衣机，Agent 不要在 render 后再手跑一遍。

---

## 禁止双跑（Checklist）

- [ ] 刚跑过 `add_package`：脚本 sync **只重渲**项目那一份时间线 → **不要**再手动 `analyze_schedule` 整盘覆盖总包；**同一回合必须**按表 B 只给新包 merge 节点（有明确到货日就写，没有就 pending）。禁止说「脚本会自动补包级节点」；禁止再手跑 sync；禁止往采购包目录写 `关键节点时间线.html`
- [ ] 业务回合 → 只跑各 `SKILL.md` 写明的入口命令；**禁止**拆 Skill 脚本翻实现、**禁止**为修小毛病当场改 Skill（发现 bug 记下来另开任务）
- [ ] 刚跑过 `dispatch_mail` / `process_email` 且 `auto: true` → **不要**再手动 render（除非修补失败字段）
- [ ] 刚跑过 `vendor-card/render_card` 且已有 `claim_form_path` / `payment-sheet.sync` → **不要**再手动 `payment-sheet` sync / 旧 `post_card_render`
- [ ] 用户丢来 MPP/PDF/**客户请款单模板** 且在系统内 → **必须**走表 B，不能指望 mailbox / `init_project` 脚本替你认模板
- [ ] Skill 0 建项没给请款单 → **必须**提醒「还没有请款单模板，请款单生成尚未启用」；禁止用技能自带样例充数
- [ ] Skill 0 建项回合用户已给请款单 → **同一回合** payment-sheet 步骤 0；不要只说「以后再认」；此时无采购包则**不要** sync
- [ ] 用户要读 PDF 正文（报价单/合同/「看这份 PDF」）→ **只用** `read-pdf`，不要用全局 `pdf` 伴侣读文字
- [ ] 邮件已由 `mail-inbox` 分类 → **不要**在 Skill 1 再发明一套意图总分类。**例外**：`Re:` / 引用原文的回信，分类器会把旧关键词判成高置信；Agent 必须读最新一段，按意图表覆写 `intent`（route.json 加 `intent_verified`）再交业务 Skill
- [ ] 单独使用功能 Skill → **不要**自动串联履约/请款/变更
- [ ] 对话里用错 Skill 改账 → 脚本会拒写（履约≠变更台账，变更≠Tracker，请款≠合同额，单独转 MPP/读 PDF≠履约数据）
- [ ] 对人只给一份时间线：`项目档案/00_进度计划/关键节点时间线.html`；不要报包内还有一张，不要把 `.skill/critical_nodes_timeline.html` 当第二份产品
- [ ] critical-nodes：**不要**把 `analyze_schedule` 字典草稿直接当定稿
- [ ] 关 `pending.json`：必须走 `pending_store.close_pending` 并声明自己的 Skill；**禁止**手改 JSON 把别人的 `status` 改成 confirmed
- [ ] 进度吃不准：**只**写 `.skill/schedule.json` 的 `pending`，禁止写入项目 `pending.json`

---

## pending.json 归属（硬拦 · 脚本）

项目 `.skill/pending.json` 是**共享待办队列**，不是谁都能改的账。闸门在基建库，不靠自觉：

```bash
python3 .cursor/lib/project-foundation/scripts/pending_store.py add \
  --project-root "/path/to/project" --skill change-flow \
  --item-json '{"reason":"out_of_order","subject":"…"}'

python3 .cursor/lib/project-foundation/scripts/pending_store.py close \
  --project-root "/path/to/project" --skill change-flow \
  --pending-id "p-…"
```

| 规则 | 怎么拦 |
|------|--------|
| 每条必须带 `skill`（是哪个 Skill 的） | 没写 / 写了不准写的名字 → 脚本报错，不落盘 |
| 每个 Skill 只能关自己的 | `close_pending` 对不上归属 → 报错，status 不动 |
| 进度 pending 留在 `schedule.json` | `critical-nodes` / `mpp-to-excel` 写 `pending.json` → 报错；`save_json` 直接写 `pending.json` 也会报错 |

**允许写 pending.json**：mail-inbox、Skill 0/1/2/3、现金流。  
**禁止写 pending.json**：进度两套、履约卡片、请款页、read-pdf（卡片提醒只留卡片顶栏；进度吃不准写 `schedule.json`）。

关单不要手改 JSON。业务 Skill 调 `pending_store`（或本 Skill 薄封装）并传入自己的 `skill`。邮件分发时代劳写入时，`skill` 仍标**负责办这件事的 Skill**（例如请款跳级标 `payment-flow`，不是 `mail-inbox`）。

---

## 对话路径用错 Skill（硬拦 · 脚本）

邮件已经按分类分给 Skill 0/1/2/3。对话里直接跑脚本，也不能拿错本子改账。闸门在基建库 `write_guard.py`：写 Tracker / 履约卡片 / Change Log 时认出调用栈里的 Skill，不对就拒写。

| 谁在跑 | 想改什么 | 脚本 |
|--------|----------|------|
| 履约（Skill 1） | Change Log | 拒写。去 Skill 3 |
| 变更（Skill 3） | Tracker 或请款栏 | 拒写。包身份归履约，请款栏归请款 |
| 请款（Skill 2） | 合同额或变更台账 | 拒写。合同额归履约，变更归 Skill 3 |
| 单独转 MPP / 读 PDF | 履约卡片、Tracker、Change Log | 拒写。只出进度 Excel/CSV 或 PDF 正文 |

请款改 Tracker 时**只许**动请款四栏；履约**不许**改已请/待请/请款进度（可以同步「下一付款节点」）。

---

## 与各 Skill / 共用库的关系（一句话）

| Skill / 库 | 角色 |
|------------|------|
| **本文**（`skill-orchestration`，Rule 配套长文，**不是 Skill**） | 编排真源；单独 vs 系统内分界 |
| Skill 0（`new-project`） | 对话建项：问齐必填（含币种和是否含税）再 `init_project`，生成 `待处理邮件/`。**给了请款单则同一回合交给 payment-sheet 认模板**。不问邮箱 |
| Skill 1（`po-flow`） | 建包起履约；**不是**邮箱总前台 |
| Skill 2（`payment-flow`） | 请款业务；不生成请款申请页 |
| Skill 3（`change-flow`） | 变更 Change Log（不写履约卡片） |
| `cashflow`（现金流，不编号） | 供应商出账现金流预测（只读） |
| `mail-inbox` | 这版唯一收件入口：扫 `待处理邮件/`、分类、路由。不连邮箱 |
| `project-foundation`（共用库，不是 Skill） | 项目骨架 / Tracker 读写；**`pending.json` 唯一写入口**（`pending_store.py`） |
| `vendor-card` | 履约条件卡片 HTML；渲完链式调 payment-sheet |
| `payment-sheet` | 认客户请款单模板（步骤 0）+ 请款申请页 / 填 Excel（步骤 1；渲卡片后自动刷页） |
| `mpp-to-excel` | MPP→人看 Excel + 机读 CSV（可单独用） |
| `critical-nodes` | 关键节点 / `schedule.json`（**Agent 主导**；可单独用） |
| `read-pdf` | 读 PDF 正文（可单独用；不抽付款节点） |
