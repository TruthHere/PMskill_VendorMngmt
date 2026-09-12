# 邮箱接入（163 IMAP · 企微 agent-mail）

## 调度形态（与 SKILL.md 一致）

| 环境 | 做法 |
|------|------|
| **企微 / WorkBuddy（推荐上线）** | Agent MCP 拉未读 → 写入 `.skill/inbox/agent_mail/*.json` → 跑 `mail-inbox/scripts/ingest_agent_mail.py`（拼 `.eml` → dispatch）。细则：`mail-inbox/references/agent-mail.md` |
| **163 IMAP（本机/旧路）** | `mail-inbox/scripts/poll_mailbox.py` 或 `run_mailbox_worker.py --once` |
| **测试期** | 终端按需跑上述入口；确认走 Cursor / WorkBuddy 对话 |

**上线（企微）示例**：

```bash
python3 /绝对路径/.cursor/skills/mail-inbox/scripts/ingest_agent_mail.py \
  --project-root "/path/to/project"
```

**上线（仍用 163 IMAP）唯一 worker**：

```bash
python3 /绝对路径/.cursor/skills/mail-inbox/scripts/run_mailbox_worker.py --once
```

**重要**：`mailbox-registry.json` 必须指向**真实项目根**（如桌面上的业务目录）。`samples/Sample-Project` 仅供演示/评测，**不要**把测试邮箱绑到样例目录。

本机 `--interval` 常驻仅调试用，不是上线目标。

## 人话流程

1. **用户**在 163（等）自行开通专用邮箱，打开 IMAP，生成**授权码**（Agent **不能**代开账号）
2. 把邮箱地址交给 Skill 0 / `init_project.py --mailbox-address ...` 做绑定
3. 授权码：对话里粘贴给 Agent → 写入项目根 `.mailbox.secret`（见下）；不要提交 Git
4. 测试期：终端或 WorkBuddy 跑 `mail-inbox` worker；上线：挂每日两轮
5. 把业务邮件转发到该邮箱

## 163 参数

| 项 | 值 |
|----|-----|
| 服务器 | `imap.163.com` |
| 端口 | `993`（SSL） |
| 用户名 | 完整邮箱，如 `TestProject_AI@163.com` |
| 密码 | **授权码**（非网页登录密码） |

网页大致路径：设置 → POP3/SMTP/IMAP → 开启 IMAP → 生成授权码。

## 本机保存授权码（推荐：对话交给 Agent）

多数使用者不会开终端。推荐流程：**用户在 Cursor / WorkBuddy 对话里粘贴授权码** → Agent 执行：

```bash
# 推荐：项目级（Worker 按项目根读取）
python3 .cursor/lib/project-foundation/scripts/set_mailbox_secret.py \
  --project-root "/path/to/project" \
  --secret "用户粘贴的授权码"
```

初始化时可一次带上：

```bash
python3 .cursor/lib/project-foundation/scripts/init_project.py \
  ... --mailbox-address "xxx@163.com" --mailbox-secret "授权码"
```

脚本会写入 `{项目根}/.mailbox.secret`（chmod 600），并确保项目 `.gitignore` 含该文件名。**不会**写入 `project.json`。Agent 汇报时勿回显明文。

仍可用的备选（熟悉终端时）：

```bash
# 环境变量
export PMSKILLS_MAIL_PASS='你的授权码'

# 或手写项目级文件
echo '你的授权码' > /path/to/project/.mailbox.secret
chmod 600 /path/to/project/.mailbox.secret
```

读取顺序见基建库 `project-foundation` 的 `read_mailbox_password`：环境变量 → 项目 `.mailbox.secret` → 库目录 / 家目录后备文件。

## 项目注册表

`init_project.py` 会把项目写入基建库目录下的 `mailbox-registry.json`（已 gitignore），或通过环境变量 `PMSKILLS_REGISTRY` 指定路径。worker 按此列表轮询。

授权码也可放在基建库根目录 `.mailbox.secret`（已 gitignore）。

## 常见错误

| 报错 | 原因 | 处理 |
|------|------|------|
| `SEARCH illegal in state AUTH` | 163 要求登录后先发 IMAP `ID`，否则 `SELECT` 失败 | 已用新版 `poll_mailbox.py` 修复；更新脚本后重试 |
| `login failed` | 用了网页密码而非授权码，或未开 IMAP | 重新生成授权码并写入 `.mailbox.secret` |
| DNS / nodename | 无网络 | 检查网络后重试 |

## 命令

```bash
# 单次拉取并处理某项目
python3 ../../mail-inbox/scripts/poll_mailbox.py --project-root "/path/to/project"

# 常驻（默认 60 秒）
python3 ../../mail-inbox/scripts/run_mailbox_worker.py --interval 60

# 只跑一轮
python3 ../../mail-inbox/scripts/run_mailbox_worker.py --once
```

## 落盘目录

```
{project}/inbox/raw/          # .eml
{project}/inbox/attachments/  # 拆出的附件
{project}/inbox/processed/    # 处理元数据
{project}/inbox/failed/       # 失败
{project}/mailbox_state.json  # 已处理 UID
```

## 置信度与确认

- 主题/正文能识别步骤 + 关键字段 → **先自动**写 `tracker.csv` / 卡片
- 缺字段 / 需拍板 → 落盘 + `pending.json`；上线经 **WorkBuddy 对话框**问用户，测试期用 Cursor 对话
- 用户确认后再写回并关闭 pending

## 换成公司邮

改 `project.json` 里 `mailbox.imap_host` / `address` / `username`，授权方式按厂商要求（常仍是应用专用密码）。脚本逻辑不用改。

## Mac launchd 模板（可选）

```xml
<!-- ~/Library/LaunchAgents/com.pmskills.mailbox.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.pmskills.mailbox</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/绝对路径/.cursor/skills/mail-inbox/scripts/run_mailbox_worker.py</string>
    <string>--interval</string>
    <string>60</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.pmskills.mailbox.plist
```
