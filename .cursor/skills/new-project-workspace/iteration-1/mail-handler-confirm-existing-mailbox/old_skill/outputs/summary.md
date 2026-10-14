# 入口 B · 确认已有项目 + 回写邮箱

## 场景

- 项目根：`HarborExisting/`（Skill 0 已初始化，`project_code=HARBOR`）
- 原邮箱：`old@163.com`
- 邮件要求：专用邮箱改为 `HarborLab_AI@163.com`

## 执行

按 OLD Skill 0 **入口 B** 运行 `handle_init_email.py`，未重建项目、未建采购包。

## 结果

| 项 | 值 |
|----|-----|
| `auto` | `true` |
| `project_code` | `HARBOR` |
| `mailbox.address`（更新前） | `old@163.com` |
| `mailbox.address`（更新后） | `HarborLab_AI@163.com` |

Handler 动作：`confirm_existing_project`、`update_mailbox`。

`.skill/project.json` 已回写邮箱地址与 `username`，并写入 `mailbox_updated_at`。
