# 邮件脱敏测试夹具

| 目录 / 文件 | 用途 |
|-------------|------|
| `raw/` | 脱敏前原始 `.eml`（**勿提交 Git**） |
| `output/` | 脱敏后 `.eml`，供 `process_email.py` 注入测试 |
| `mapping.example.json` | 对照表示例（可提交） |
| `mapping.json` | 你的真实对照表（已 gitignore） |

## 批量脱敏（本机终端）

```bash
SKILL="$HOME/Documents/AI Projects/PMskills/.cursor/skills/po-flow"

# 1) 准备对照表（首次）
cp "$SKILL/tests/redact/mapping.example.json" "$SKILL/tests/redact/mapping.json"

# 2) 把待脱敏 .eml 放进 raw/，或直接指定任意文件夹
python3 "$SKILL/scripts/redact_eml_batch.py" \
  --mapping "$SKILL/tests/redact/mapping.json" \
  --input "$SKILL/tests/redact/raw" \
  --output "$SKILL/tests/redact/output"
```

也可对桌面整夹跑：

```bash
python3 "$SKILL/scripts/redact_eml_batch.py" \
  --mapping "$SKILL/tests/redact/mapping.json" \
  --input "$HOME/Desktop/untitled folder" \
  --output "$SKILL/tests/redact/output"
```

## 脚本会做什么

- 改 Subject / From / To / Cc（可强制测试邮箱）
- 按 mapping 替换正文 plain/html
- 文本类附件、嵌套 `.eml` 同步替换
- PDF 换成占位 PDF（无法安全改二进制原文）
- 图片附件保留（文件名可替换）；签名区可不专门处理

注入测试建议写到 `test-runs/<某次运行>/`，不要写入桌面业务项目。
