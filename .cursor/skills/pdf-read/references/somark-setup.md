# SoMark 密钥配置（跨平台）

`pdf-read` 通过 **同一套解析链** 找 API Key，不依赖 Cursor MCP。在 Cursor、WorkBuddy、终端手动跑脚本时行为一致。

## 解析顺序（先命中先用）

| 优先级 | 位置 | 适用场景 |
|--------|------|----------|
| 1 | 环境变量 `SOMARK_API_KEY` | CI、平台注入、临时覆盖 |
| 2 | `<项目根>/.somark.secret` | 某项目专用 Key（少见） |
| 3 | `.cursor/skills/pdf-read/.somark.secret` | **推荐**：Skill 随仓库/拷贝走，跨平台同一文件 |
| 4 | `~/.pmskills/somark.secret` | 本机所有项目共用一把 Key |

文件内容：**一行 API Key**，或 `SOMARK_API_KEY=sk-...` 均可。

## 一次性配置（推荐）

```bash
# 从 https://somark.cn/workbench/apikey 复制 Key
echo 'sk-your-api-key' > .cursor/skills/pdf-read/.somark.secret
chmod 600 .cursor/skills/pdf-read/.somark.secret

pip install -r .cursor/skills/pdf-read/scripts/requirements.txt
pip install somark
```

## 换平台时怎么带 Key？

| 方式 | 做法 |
|------|------|
| **拷贝 Skill 目录** | 连同 `.somark.secret` 一起复制（已在 gitignore，不会进 Git） |
| **本机统一** | 各平台机器都写 `~/.pmskills/somark.secret`，内容相同 |
| **平台环境变量** | 在 WorkBuddy / 服务器上设 `SOMARK_API_KEY` |

## 与 MCP 的关系

- **Skill 脚本路径**（本 Skill）：`read_pdf.py` → `somark` CLI，Key 走上面解析链。
- **MCP 路径**（可选）：在 Cursor 里另配 `somark-mcp`，Key 写在 MCP 的 `env.SOMARK_API_KEY`。
- 两把 Key **可以是同一个**；Skill 不依赖 MCP 是否启用。

## 验证

```bash
python3 .cursor/skills/pdf-read/scripts/classify_pdf.py --pdf "/path/to/file.pdf"
python3 .cursor/skills/pdf-read/scripts/read_pdf.py \
  --pdf "/path/to/scan.pdf" \
  --project-root "/path/to/project" \
  --out /tmp/read.json
```
