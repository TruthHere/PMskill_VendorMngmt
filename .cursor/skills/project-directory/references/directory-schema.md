# 通讯录底账（directory.json）

路径：`{项目根}/.skill/directory.json`

Excel 每次从这份 JSON **整表重写**。

## 结构

```json
{
  "version": 1,
  "channel": "wecom_group",
  "project_name": "…",
  "group_message_path": "…/群消息.txt",
  "fill_form_path": "…/填写页.html",
  "requests": [
    {
      "package_name": "BMS",
      "status": "posted",
      "channel": "wecom_group",
      "posted_at": "…",
      "replied_at": ""
    }
  ],
  "contacts": [
    {
      "package_name": "BMS",
      "name": "张三",
      "title": "项目经理",
      "phone": "13800138000",
      "email": "zhangsan@vendor.com",
      "source": "group"
    }
  ]
}
```

## requests.status

| 值 | 对人说 |
|----|--------|
| `ready` | 群消息已写好，还没发到群 |
| `posted` | 已发到群，等回复 |
| `replied` | 已解析到至少一位对接人 |

旧值 `sent` / `draft` / `missing_email` 读入时仍能显示，新写入只用上表。

## 回执写入规则

- 同一采购包、同一邮箱 → 更新，不另起一行
- 新邮箱或新姓名 → 追加
- 姓名和邮箱都空 → 丢弃
- 对不上采购包 → pending，不要写到别的包

通道：`group`（群粘贴）或 `fill_form`（填写页 JSON）。
