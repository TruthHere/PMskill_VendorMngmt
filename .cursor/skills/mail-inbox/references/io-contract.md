# mail-inbox 输入 / 输出契约

## 输入

任选其一（可组合）：

| 来源 | 字段 |
|------|------|
| IMAP 拉取 | `--project-root`；读项目 `project.json` / mailbox secret |
| 企微 agent-mail JSON | `ingest_agent_mail.py --message-json` 或 drop 目录 `.skill/inbox/agent_mail/*.json`（见 `agent-mail.md`） |
| 本地 `.eml` | `--eml /path/to/file.eml` |
| 粘贴全文 | `--subject` + `--body`（+ 可选附件路径） |

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
  "route_to": "contract-fulfillment-struct",
  "confidence": "high",
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
    "skill": "contract-fulfillment-struct",
    "action": "handle_fulfillment_rfp",
    "note": "业务 Skill 消费本 JSON；mail-inbox 不改业务数据"
  }
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `intent` | 是 | 见 `intent-taxonomy.md` |
| `route_to` | 是 | `project-init` \| `contract-fulfillment-struct` \| `change-archive` \| `payment-request` \| `null` |
| `confidence` | 是 | `high` \| `medium` \| `low` |
| `eml_path` | 建议 | 已落盘路径；粘贴模式可先写 inbox |
| `hints.*` | 否 | 线索（`package_name` / `supplier_hint` / `change_no` 等），业务侧可覆盖 |
| `enrichment.*` | 否 | 附加标记，不改 intent |
| `pending` | 否 | 需问人时非 null |
| `did` | 是 | 编排用；业务侧勿重复 ingest |
| `next` | 是 | 建议下游；执行权在调用方 / worker |

### pending

写入项目 `.skill/pending.json` 时必须带 `skill`（负责办这件事的 Skill，例如低置信分类是 `mail-inbox`，请款跳级是 `payment-request`）。关单只能由该 Skill 走 `pending_store.close_pending`。

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
| `project_init` | `project-init` |
| `fulfillment.*` | `contract-fulfillment-struct` |
| `change.*` | `change-archive` |
| `payment_claim.*` | `payment-request` |
| `unknown` | `null`（只 pending） |

## 消费方契约

1. 只处理指向自己、且非强制 pending 的邮件。  
2. 禁止再发明一套总分类（可做字段精炼）。  
3. 变更阶段细则仍遵 Skill 3 `email-stages.md`。  
4. `fulfillment.rfp` + `enrichment.payment_terms` → Skill 1 顺带写付款节点。  
5. 业务输出带 `did`，遵守 `skill-orchestration` 禁止双跑。

## 非目标

- 不在本 Skill 内 `render_card` / `update_tracker` / 写 Change Log  
- 不解析 MPP / 合同 PDF（只打 `schedule_attachment` 等标记）  
- 不替代 `pdf-read`
