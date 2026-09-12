# agent-mail → 邮局（WorkBuddy / 企微）

人话：企微邮箱把信拿进来；本 Skill 把结构化 JSON **拼成标准 `.eml`**，再走原来的分拣。

## 谁干什么

| 谁 | 干什么 |
|----|--------|
| WorkBuddy Agent（MCP） | `ListMessages` / `GetMessage` / 下附件；写入项目 `.skill/inbox/agent_mail/*.json` |
| **本 Skill** `ingest_agent_mail.py` | JSON → `.eml` → `dispatch_mail` → 记 `processed_msg_ids` |
| Skill 0/1/2/3 | 不动 |

## `project.json` 邮箱（可选提示）

```json
"mailbox": {
  "source": "agent_mail",
  "alias_id": "",
  "address": "你的企微邮箱地址"
}
```

`source` 也可为 `imap`（默认走 `poll_mailbox`）。**ingest 不强制读 source**，有 JSON 就能吃；填上是给人看、给 automation 选入口。

IMAP 字段（`imap_host` 等）可保留作本机兜底，不冲突。

## 命令

```bash
# 处理 drop 目录里所有 JSON
python3 .cursor/skills/mail-inbox/scripts/ingest_agent_mail.py \
  --project-root "/path/to/project"

# 指定一封
python3 .cursor/skills/mail-inbox/scripts/ingest_agent_mail.py \
  --project-root "/path/to/project" \
  --message-json "/path/to/msg.json"

# 只拼 .eml、不分发
python3 .cursor/skills/mail-inbox/scripts/ingest_agent_mail.py \
  --project-root "/path/to/project" \
  --message-json "…" --no-process
```

只拼文件、不入项目：

```bash
python3 .cursor/skills/mail-inbox/scripts/build_eml_from_agent_mail.py \
  --message-json "…" --out "/tmp/out.eml"
```

## JSON 最小字段

`message_id`（或 `msg_id` / `id`）、`subject`、`from`、`to`、`body`（或 `body_text`）、可选 `date` / `cc` / `body_format`（`text`|`html`）、`attachments: [{filename, path}]`。

样例：`samples/agent_mail/`。

## 状态

`.skill/mailbox_state.json` 增加 `processed_msg_ids`（企微 `msg_…`）。IMAP 的 `processed_uids` 仍保留。
