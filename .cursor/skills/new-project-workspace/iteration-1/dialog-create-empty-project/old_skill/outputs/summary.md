# 对话建项 · Harbor Lab — 执行摘要（OLD skill snapshot）

## 任务

按 Skill 0（OLD snapshot）从初始化邮件字段创建空项目，不建采购包，无进度计划附件。

## 提取字段

| 字段 | 值 |
|------|-----|
| 项目名称 | Harbor Lab |
| 项目编号 | HARBOR |
| 项目类型 | 实验室 |
| 项目地址 | 上海市浦东新区张江路 88 号 |
| 甲方名称 | 港湾科技有限公司 |
| 项目经理 | 李四 |
| 币种/含税 | CNY 含税 |
| 专用邮箱 | HarborLab_AI@163.com |
| 本地根路径 | `.../old_skill/outputs/HarborLab` |

## 执行命令

快照 `run_init.py` 因 foundation 路径解析错误失败，改按 SKILL.md「标准命令」直接调用 foundation：

```bash
python3 .cursor/skills/project-foundation/scripts/init_project.py \
  --root "/Users/truth_here/Documents/AI Projects/PMskills/.cursor/skills/new-project-workspace/iteration-1/dialog-create-empty-project/old_skill/outputs/HarborLab" \
  --name "Harbor Lab" \
  --code "HARBOR" \
  --type "实验室" \
  --address "上海市浦东新区张江路 88 号" \
  --client "港湾科技有限公司" \
  --pm "李四" \
  --currency "CNY 含税" \
  --mailbox-address "HarborLab_AI@163.com"
```

- 退出码：0
- 未使用 `--schedule-csv`（prompt 明确无进度计划附件）

## 产出路径

| 项 | 路径 |
|----|------|
| 项目根 | `/Users/truth_here/Documents/AI Projects/PMskills/.cursor/skills/new-project-workspace/iteration-1/dialog-create-empty-project/old_skill/outputs/HarborLab` |
| project.json | `.../HarborLab/.skill/project.json` |
| Tracker CSV | `.../HarborLab/Harbor Lab_procurement_packages_status_tracker.csv` |
| Tracker XLSX | `.../HarborLab/Harbor Lab_procurement_packages_status_tracker.xlsx` |
| 项目背景 | `.../HarborLab/项目背景.md` |

## 完成检查

- [x] `.skill/project.json` 含 `project_name`、`project_code`
- [x] 空 Tracker（csv/xlsx）与 `项目背景.md` 已创建
- [x] 专用邮箱 `HarborLab_AI@163.com` 已写入 `mailbox.address`
- [x] 无进度附件，跳过表 B 编排
- [x] 未建采购包目录
- [x] 已提示可转发 RFP（Skill 1）

## 后续提醒

1. 在 163 邮箱后台为 `HarborLab_AI@163.com` 配置 IMAP 授权码（勿提交 Git，见 `po-flow/references/mailbox-setup.md`）。
2. 空项目已就绪，可开始转发 RFP 邮件进入 **Skill 1（po-flow）** 建包流程。
