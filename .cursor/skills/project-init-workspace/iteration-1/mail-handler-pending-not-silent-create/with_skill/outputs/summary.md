# 入口 B 处理结果 · Ghost Proj

## 本次 handler 做了什么

邮局入口 `handle_init_email.py` 已处理 `[项目初始化] Ghost Proj - GHOST` 邮件。

- **reason**: `project_not_initialized`
- **auto**: `false`（未自动确认/建项）
- **pending_id**: `p-9T1430580800`
- **project.json 是否存在**: 否（符合 Skill 0 设计——handler 不静默建半残项目）

handler 已从邮件正文抽取字段并写入 `GhostRoot/.skill/pending.json`，等待人工补建。

## 下一步：入口 A · 对话建项

请 PM 或 Agent 在对话中确认根路径与必填项后，运行 **入口 A** 补建空项目：

```bash
python3 .cursor/skills/project-init/scripts/run_init.py \
  --root "/Users/truth_here/Documents/AI Projects/PMskills/.cursor/skills/project-init-workspace/iteration-1/mail-handler-pending-not-silent-create/with_skill/outputs/GhostRoot" \
  --name "Ghost Proj" \
  --code "GHOST" \
  --type "实验室" \
  --address "上海市某处" \
  --client "Ghost Co" \
  --pm "王五" \
  --currency "CNY 含税"
```

### 工作流 A 要点（Skill 0）

1. 核对邮件字段与根路径是否与 PM 预期一致（缺项先问，勿猜）。
2. 运行 `run_init.py` 创建 `.skill/project.json`、空 Tracker、`项目背景.md`。
3. 若邮件含专用邮箱，补 `--mailbox-address` 并提醒配置授权码（勿提交 Git）。
4. 若有进度附件：归档到 `项目档案/00_进度计划/` → 按 skill-orchestration 表 B 编排 mpp-excel → critical-nodes。
5. 建项完成后 pending 可视为已消化；后续同类初始化邮件可走入口 B 自动确认（`auto: true`）。
6. 提示可开始转发 RFP（Skill 1）。

**禁止**：绕过 pending 直接 mkdir / 手写 `project.json`，或在 handler 路径静默 `init_project`。
