---
name: skill-orchestration
description: >-
  项目级 Skill 编排真源：全局原则「先理解再处理」；规定各 Skill 谁先谁后、脚本串什么、
  Agent 跑什么、禁止双跑；区分「功能 Skill 单独使用」与「供应商履约整套系统内协作」。
  务必在用户或 Agent 涉及多 Skill 协作、进度/合同/邮件/建包/请款/变更交叉、
  或不确定该调哪个 Skill 时使用。
---

# Skill 编排（项目级 · 唯一真源）

**固定工序靠脚本串；需要理解/判断才交给 Agent。**  
其它文档若与本文冲突，**以本文为准**。

## 全局原则 · 先理解再处理

适用于本仓库**整套供应商管理 Skill**（Skill 0/1/2/3/4/5、mail-inbox、履约卡片、进度、PDF 等），不单属某一业务 Skill。

| 要 | 不要 |
|----|------|
| 先搞清：来件/文件在办哪一步、附件是什么、关键数字与结论在哪 | 只拿表头/关键词去套旧正则就当结论 |
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
| `schedule-mpp-excel` | `.mpp`/XML/粗表 → Project 视图 Excel + 机读 CSV | 归档到 `00_进度计划/`；交给 critical-nodes |
| `schedule-critical-nodes` | **Agent**读懂进度 → 推理关键节点 → `write_critical_nodes` 落盘（+ 可选时间线） | 建包后 sync **只重渲**时间线；卡片读 `window_end` |
| `pdf-read` | PDF → 统一 JSON/Markdown（只读正文，不抽付款节点） | Skill 1 步骤 4a 先读正文；付款节点由 Skill 1 抽取后写入卡片/Tracker |
| `payment-form` | **只**刷请款申请页 / 出公司 Excel（不入账） | 渲卡片后由 fulfillment-card 自动调用；单独精调请款页时只跑本 Skill |
| `cashflow-forecast` | **只读**聚合 Tracker / schedule / 变更 → 按月出账预测 | 用户要看现金流时重算；**不写**履约/请款/变更 |
| `project-directory` | 群消息 + 填写页收集对接人 → 项目通讯录 Excel | 用户要联系方式时生成群文案/收录群回复；**不走邮箱、不写 Tracker** |

单独使用时：**禁止**因为「系统里还要刷卡片/请款」而擅自改履约数据。

---

## 人话版（系统内）

| 情况 | 谁负责「下一步」 | 大模型要不要参与编排 |
|------|------------------|----------------------|
| 收邮件、建包、改完卡片刷新请款页 | **脚本**按写死顺序做完 | 不要（编排层） |
| 用户扔来 MPP / 合同 PDF；字段吃不准要问人 | **Agent** Read 功能 Skill 再跑 | 要 |

「请款同步」= 改完 `card-data` 并调用 **fulfillment-card** `render_card.py` 后，脚本会再调 **payment-form**，同包 `请款申请.html` 已**一并刷新**。Skill 1 / Skill 2 **不要**再单独刷请款页（除非只要刷页、不改卡片）。

---

## 目标架构（系统内 · 冻结）

### 定版原则

0. **先理解再处理**（上文全局原则）：先读懂来件与附件，再分类/落库/推进状态。
1. **唯一收信入口**：`mail-inbox` 的 `poll_mailbox` / `run_mailbox_worker`。
2. **唯一分类**：只 `mail-inbox/scripts/classify_mail.py`。
3. **唯一分发**：只 `mail-inbox/scripts/dispatch_mail.py` → Skill 0/1/2/3 handlers。
4. **Skill 1 只做履约**：建包起；只消费 `fulfillment.*`。
5. **功能 Skill 不写业务流程**：MPP/节点/PDF 的「在系统里谁先谁后」只写在本文，不写回三个功能 Skill 正文。

### 理想调用链（邮件）

```text
IMAP / .eml
  → mail-inbox（收 + 分）
       ├─ project_init        → Skill 0（project-init）
       ├─ fulfillment.*       → Skill 1（contract-fulfillment-struct）
       ├─ payment_claim.*     → Skill 2（按五步推进请款；仅客户批复占用节点）
       ├─ change.*            → Skill 3（change-archive）
       └─ unknown / 低置信    → pending 问人
```

---

## 总原则

1. **先理解再处理**（全局，见上）：理解先于落库与编排动作。
2. **一条入口一种编排**：脚本已串完的下游，Agent **同一回合禁止再手搓一遍**。
3. **看输出再决定**：入口脚本若返回 `did: [...]` / `claim_form_path` / `schedule_timeline`，视为已完成对应步骤。
4. **需要判断的一次性任务**：Agent 必须 Read 对应功能 Skill，禁止在业务 Skill 里手猜（尤其日期、付款节点）。
5. **单独 vs 系统**：触发词只命中功能能力、且用户未提履约/请款/变更 → 走「单独使用」；否则走系统内表 A/B。

---

## 表 A · 脚本编排（偏洗衣机）

入口脚本自己串下游；Agent 只处理结果 / pending，**不要重复调用「已自动」列**。

| 入口 | 脚本自动做什么 | Agent 还要做什么 | 禁止 |
|------|----------------|------------------|------|
| `mail-inbox` worker / `dispatch_mail.py` | classify → 按 `route_to` 调 Skill 0/1/2/3 | 确认 `pending.json`；歧义提问 | 再手搓分类；绕过邮局直调多 Skill |
| `process_email.py`（经 dispatch） | 归档、更新 Tracker、调 fulfillment-card | 确认 pending | 逐步手调 render / 再 sync 请款页 |
| `update_tracker.py --action add-package` | → `schedule-critical-nodes/sync_schedule_timeline.py`（有已有 critical_nodes 时**只重渲**时间线；不覆盖节点） | 汇报建包；看 timeline 是否 skipped | 建包后立刻再手跑 analyze 覆盖节点（除非用户要强制草稿重算） |
| `fulfillment-card/render_card.py` | → 履约卡片 HTML → 自动调 **payment-form** 刷请款申请.html | 确认两路径；有 `claim_form_path` / `did` 含 `payment-form.sync` 即完成 | 渲染后再手跑 payment-form sync / 旧 `post_card_render` |
| `payment-form/sync_claim_form.py` | → 只刷请款申请.html（+ `.claim-assets`）；Variations 读 Change Log | 用户只要精调/重刷请款页时用 | 系统内刚跑过 render_card 已有 claim_form_path 时再手跑一遍 |
| Skill 3 `handle_change_email` | 只更新 Change Log + 归档 | 一般无需另操作 | 为变更去改采购包 Tracker / 写履约卡片 |
| `project-directory/compose_group_post.py` | 写群消息 + 填写页 + 重写通讯录 Excel | 把群文案给用户复制；用户说已发到群则 `--mark-posted` | 走邮箱 SMTP；建包回合偷偷刷群 |

Skill 1 对话里改卡片：只调一次渲染：

```bash
python3 .cursor/skills/fulfillment-card/scripts/render_card.py --package-dir "…" --patch '{…}'
```

---

## 表 B · Agent 编排（偏要动脑）

| 触发 | Agent 必须 | 禁止 |
|------|------------|------|
| `.mpp` / Project XML / Master Schedule / 甘特（**系统内**） | Read+执行 `schedule-mpp-excel` → **Agent 主导** `schedule-critical-nodes`（理解→推理→`write_critical_nodes`）→ 对各包 `fulfillment-card` render | 不读进度瞎填日期；只归档不解析 |
| 同上但用户**只要转 Excel / 只要关键节点**（单独使用） | 只跑对应功能 Skill，停在其输出 | 擅自改卡片 / Tracker / 请款 |
| 已是合规 `*_schedule.csv`（系统内） | 可跳过 mpp-excel；仍须 critical-nodes（Agent）→ 卡片 | 同上 |
| 合同 / 报价 PDF（Skill 1 步骤 4a） | Read+执行 `pdf-read` 读正文 → Skill 1 `extract_contract_pdf.py` 抽付款节点候选 → PM 确认后写卡片 | 绕过 pdf-read 全本渲图 / 自装 OCR；让 pdf-read 抽付款节点；用全局 pdf 伴侣读文字 |
| 用户只要读 PDF / OCR（单独使用） | 只跑 `pdf-read`；把 JSON/MD 交给用户 | 擅自写入履约卡片；改去用全局 pdf 伴侣读文字 |
| 用户明确说「重算关键节点 / 重刷时间线」 | 走 critical-nodes（Agent 重推理 + write；或仅 `render_timeline`） | 改 Skill 1 冒充进度解析；用字典 analyze 直接当定稿 |
| PM 在时间线改节点后保存 / apply | 写回 `schedule.json`、重渲时间线（**不**默认刷履约卡片） | 只改 HTML 不落 `schedule.json`；用推断覆盖 `manual` |
| 字段置信不足 / 变更歧义 / 请款抽不出关键字段 | 写入或认领 **本 Skill 自己的** `pending`，问人 | 静默当定稿；关别人的 pending；把进度 pending 写进 `pending.json` |
| 收集供应商联系方式 / Project Directory | Read+执行 `project-directory`（群消息 + 填写页；贴群回复 ingest） | 发邮件；改 Tracker；建包时偷偷刷群 |

进度细节：`references/schedule-pipeline.md`（本目录）。  
PDF 细节：`references/pdf-pipeline.md`（本目录）。  
二者服从本文「谁编排」划分。

---

## 进度计划链路（系统内强制）

```text
.mpp / Project XML
  → ① schedule-mpp-excel
       → *_schedule.csv + *_project_view.xlsx
  → ② schedule-critical-nodes（**Agent 理解 + 推理** → write_critical_nodes）
       → .skill/schedule.json + 时间线 HTML
  → ③ fulfillment-card/render_card.py
       → 履约卡片「计划时间区间」
       →（自动）payment-form → 请款申请页
```

已是 `.csv` / `.xlsx` 任务表：可跳过 ①，从 ② 开始。  
**禁止**在履约 Skill 内不读进度瞎猜日期。细则见 `references/schedule-pipeline.md`。

---

## 合同 PDF 链路（系统内 · 步骤 4a）

```text
合同 / 报价 PDF
  → pdf-read/scripts/read_pdf.py          # 只出正文 JSON/Markdown
  → Skill 1 extract_contract_pdf.py --read-json …
       → payment_nodes 候选（启发式）
  → PM 确认 → fulfillment-card / Tracker
```

**禁止**默认全本渲图。细则见 `references/pdf-pipeline.md`。

---

## 禁止双跑（Checklist）

- [ ] 刚跑过 `add_package` 且未要求「强制重算」→ **不要**再手动 `analyze_schedule` 覆盖节点 / 不必再 sync（脚本已重渲）
- [ ] 刚跑过 `dispatch_mail` / `process_email` 且 `auto: true` → **不要**再手动 render（除非修补失败字段）
- [ ] 刚跑过 `fulfillment-card/render_card` 且已有 `claim_form_path` / `payment-form.sync` → **不要**再手动 `payment-form` sync / 旧 `post_card_render`
- [ ] 用户丢来 MPP/PDF 且在系统内 → **必须**走表 B，不能指望 mailbox 脚本替你解析文件类型
- [ ] 用户要读 PDF 正文（报价单/合同/「看这份 PDF」）→ **只用** `pdf-read`，不要用全局 `pdf` 伴侣读文字
- [ ] 邮件已由 `mail-inbox` 分类 → **不要**在 Skill 1 再发明一套意图总分类
- [ ] 单独使用功能 Skill → **不要**自动串联履约/请款/变更
- [ ] 对话里用错 Skill 改账 → 脚本会拒写（履约≠变更台账，变更≠Tracker，请款≠合同额，单独转 MPP/读 PDF≠履约数据）
- [ ] 刚 ingest 过通讯录群回复且已有 `xlsx_path` → **不要**再手搓同一段回复
- [ ] critical-nodes：**不要**把 `analyze_schedule` 字典草稿直接当定稿
- [ ] 关 `pending.json`：必须走 `pending_store.close_pending` 并声明自己的 Skill；**禁止**手改 JSON 把别人的 `status` 改成 confirmed
- [ ] 进度吃不准：**只**写 `.skill/schedule.json` 的 `pending`，禁止写入项目 `pending.json`

---

## pending.json 归属（硬拦 · 脚本）

项目 `.skill/pending.json` 是**共享待办队列**，不是谁都能改的账。闸门在基建库，不靠自觉：

```bash
python3 .cursor/lib/project-foundation/scripts/pending_store.py add \
  --project-root "/path/to/project" --skill change-archive \
  --item-json '{"reason":"out_of_order","subject":"…"}'

python3 .cursor/lib/project-foundation/scripts/pending_store.py close \
  --project-root "/path/to/project" --skill change-archive \
  --pending-id "p-…"
```

| 规则 | 怎么拦 |
|------|--------|
| 每条必须带 `skill`（是哪个 Skill 的） | 没写 / 写了不准写的名字 → 脚本报错，不落盘 |
| 每个 Skill 只能关自己的 | `close_pending` 对不上归属 → 报错，status 不动 |
| 进度 pending 留在 `schedule.json` | `schedule-critical-nodes` / `schedule-mpp-excel` 写 `pending.json` → 报错；`save_json` 直接写 `pending.json` 也会报错 |

**允许写 pending.json**：mail-inbox、Skill 0/1/2/3、现金流、通讯录。  
**禁止写 pending.json**：进度两套、履约卡片、请款页、pdf-read（卡片提醒只留卡片顶栏；进度吃不准写 `schedule.json`）。

关单不要手改 JSON。业务 Skill 调 `pending_store`（或本 Skill 薄封装）并传入自己的 `skill`。邮件分发时代劳写入时，`skill` 仍标**负责办这件事的 Skill**（例如请款跳级标 `payment-request`，不是 `mail-inbox`）。

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
| **本 Skill** | 编排真源；单独 vs 系统内分界 |
| Skill 0（`project-init`） | 项目初始化：对话建项（init_project）/ 邮局确认或 pending（不静默建项） |
| Skill 1（`contract-fulfillment-struct`） | 建包起履约；**不是**邮箱总前台 |
| Skill 2（`payment-request`） | 请款业务；不生成请款申请页 |
| Skill 3（`change-archive`） | 变更 Change Log（不写履约卡片） |
| Skill 4（`cashflow-forecast`） | 供应商出账现金流预测（只读） |
| Skill 5（`project-directory`） | 项目通讯录：群消息 / 填写页 → Excel（不走邮箱） |
| `mail-inbox` | 唯一收信 / 分类 / 路由 |
| `project-foundation`（共用库，不是 Skill） | 项目骨架 / Tracker 读写；**`pending.json` 唯一写入口**（`pending_store.py`） |
| `fulfillment-card` | 履约条件卡片 HTML；渲完链式调 payment-form |
| `payment-form` | 请款申请页 HTML + 公司模板 Excel |
| `schedule-mpp-excel` | MPP→人看 Excel + 机读 CSV（可单独用） |
| `schedule-critical-nodes` | 关键节点 / `schedule.json`（**Agent 主导**；可单独用） |
| `pdf-read` | 读 PDF 正文（可单独用；不抽付款节点） |
