# mail-inbox 输入 / 输出契约

## 输入

这版给人用的入口：项目根 `待处理邮件/` 里的整封 `.eml`，或 Outlook 另存的 `.msg`。`.msg` 先转成 `.eml`，再分类。

```bash
python3 <skills-root>/mail-inbox/scripts/process_drop_folder.py \
  --project-root "/path/to/project"
```

下面这些不是这版步骤（脚本还在，不要教用户去连）：

| 来源 | 字段 |
|------|------|
| 本地单封 `.eml`（补处理） | `dispatch_mail.py --eml` |
| IMAP 拉取 | 旧路，这版不用 |
| 企微 agent-mail JSON | 旧路，这版不用 |

```bash
python3 .cursor/skills/mail-inbox/scripts/classify_mail.py \
  --project-root "/path/to/project" \
  --eml "/path/to/msg.eml"
```

## 输出（stdout JSON · 单封 · 与现行 classify 对齐）

```json
{
  "ok": true,
  "eml_path": "/path/to/msg.eml",
  "intent": "fulfillment.rfp",
  "route_to": "po-flow",
  "confidence": "high",
  "intent_verified": true,
  "project_root": "/path/to/project",
  "hints": {
    "package_name": "BMS",
    "supplier_hint": "Schneider",
    "change_no": "",
    "subject": "…"
  },
  "enrichment": {
    "payment_terms": true,
    "has_quote_attachment": false,
    "has_drawing": false,
    "schedule_attachment": false
  },
  "attachments": [
    {"filename": "quote.xlsx", "kind": "quote"}
  ],
  "pending": null,
  "did": ["ingest", "classify"],
  "next": {
    "skill": "po-flow",
    "action": "handle_fulfillment_rfp",
    "note": "业务 Skill 消费本 JSON；mail-inbox 不改业务数据"
  }
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `intent` | 是 | 见 `intent-taxonomy.md` |
| `route_to` | 是 | `new-project` \| `po-flow` \| `change-flow` \| `payment-flow` \| `null` |
| `confidence` | 是 | `high` \| `medium` \| `low` |
| `intent_verified` | 否 | Agent 已读最新一段并确认/覆写 intent 后为 `true`。已建包上的 `Re:` 被判成 RFP 时，无此标记则 Skill 1 会 pending，不自动当新 RFP |
| `eml_path` | 建议 | 已落盘路径；粘贴模式可先写 inbox |
| `hints.*` | 否 | 线索（`package_name` / `supplier_hint` / `change_no` 等），业务侧可覆盖 |
| `enrichment.*` | 否 | 附加标记，不改 intent |
| `pending` | 否 | 需问人时非 null |
| `did` | 是 | 编排用；业务侧勿重复 ingest |
| `next` | 是 | 建议下游；执行权在调用方 / worker |

### pending

写入项目 `.skill/pending.json` 时必须带 `skill`（负责办这件事的 Skill，例如低置信分类是 `mail-inbox`，请款跳级是 `payment-flow`）。关单只能由该 Skill 走 `pending_store.close_pending`。

```json
{
  "pending": {
    "reason": "package_ambiguous",
    "question": "无法唯一匹配采购包，候选：BMS / EPMS？",
    "candidates": ["BMS", "EPMS"]
  }
}
```

常见 `reason`：`package_ambiguous` \| `change_no_ambiguous` \| `intent_low_confidence` \| `missing_project`。

### 批量 / worker

```json
{
  "ok": true,
  "project_root": "…",
  "processed": 3,
  "results": [],
  "did": ["poll_imap", "classify_batch"],
  "next_agent": ["resolve open pending only"]
}
```

## 路由表

| intent 前缀 | route_to |
|-------------|----------|
| `project_init` | `new-project` |
| `fulfillment.*` | `po-flow` |
| `change.*` | `change-flow` |
| `payment_claim.*` | `payment-flow` |
| `unknown` | `null`（只 pending） |

## 消费方契约

1. 只处理指向自己、且非强制 pending 的邮件。  
2. 禁止再发明一套总分类（可做字段精炼）。线程回信允许 Agent **覆写** `intent`（必须仍是本表的值），并设 `intent_verified: true`。`confidence: high` 不等于判对——见 `intent-taxonomy.md`「线程回信怎么判」。  
3. 变更阶段细则仍遵 Skill 3 `email-stages.md`。  
4. `fulfillment.rfp` + `enrichment.payment_terms` → Skill 1 顺带写付款节点。  
5. 业务输出带 `did`，遵守 `skill-orchestration` 禁止双跑。

## 非目标

- 不在本 Skill 内 `render_card` / `update_tracker` / 写 Change Log  
- 不解析 MPP / 合同 PDF（只打 `schedule_attachment` 等标记）  
- 不替代 `read-pdf`
