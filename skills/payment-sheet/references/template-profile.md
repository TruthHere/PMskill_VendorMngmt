# 从客户请款单模板生成填写页

**换项目 / 换业主时必做。** 只认用户交来的那张客户请款单，不要拿别的项目或技能自带样例去套。

**核心：** 客户原来那张表就是底稿。清空要填的格子，再写入本包信息。不要重做一张表。

## 人话流程

1. 用户拿出客户的标准请款单（**只收 `.xlsx`**。`.xls` / Word 先不接，提醒换成 `.xlsx` 再认）。
2. 跑体检脚本，列出每张表、有字的格子、公式、旁边有标签的空格。
3. **Agent 先读懂**（先理解再处理），起草对照表：网页上填什么 → Excel 哪一格。
4. 用白话把对照表念给用户听，**点头后再落盘**。吃不准就问，不要猜完直接用。
5. 把模板和对照表装进项目 `.skill/payment-sheet/`，再刷各包「请款申请.html」。

## 命令

只体检（不改项目）：

```bash
python3 .cursor/skills/payment-sheet/scripts/inspect_payment_template.py \
  --xlsx "/path/to/客户请款单.xlsx" \
  --out-md "/tmp/template-inspect.md"
```

装进项目（先出草稿对照表）：

```bash
python3 .cursor/skills/payment-sheet/scripts/adopt_payment_template.py \
  --xlsx "/path/to/客户请款单.xlsx" \
  --project-root "/path/to/项目根" \
  --title "客户名 请款单"
```

用户确认对照表之后，把改好的 `template-profile.json` 再装一次：

```bash
python3 .cursor/skills/payment-sheet/scripts/adopt_payment_template.py \
  --xlsx "/path/to/客户请款单.xlsx" \
  --project-root "/path/to/项目根" \
  --profile "/path/to/template-profile.json"
```

然后对采购包刷请款页：

```bash
python3 .cursor/skills/payment-sheet/scripts/sync_claim_form.py \
  --package-dir "/path/to/01_xxx_Vendor"
```

## 落盘位置

```
{项目根}/.skill/payment-sheet/
  template.xlsx            # 客户原件副本，下载时版式一比一
  template-profile.json    # 对照表（网页字段 → 格子）
  template-inspect.md      # 体检给 Agent 读
```

`project.json` 会记下：

```json
"payment_form": {
  "template": ".skill/payment-sheet/template.xlsx",
  "profile": ".skill/payment-sheet/template-profile.json"
}
```

没有这两份文件时，请款单生成**未启用**：填写页只提醒「还没有请款单模板」。不要用技能自带样例充数。

## 往原表里填（和填表脚本同一条规矩）

认进项目的必须是客户原件的 `.xlsx` 副本。先清空对照表里标了要填的格子，再往这些格子写本包信息。图片、换行、合并格不动。  
不是 `.xlsx` 就拒绝，不要转换、不要重画。样例数字用 `clear_on_adopt` 只清空那些格子。

## template-profile.json

| 键 | 说明 |
|----|------|
| `engine` | `cells` = 按 `writes` 逐格写；明细区要插既往请款行时写 `insert_rows`。**只看本项目对照表，不要按业主品牌猜** |
| `amount_tax` | `incl` = 模板按含税填；缺省 `excl` 不含税。填写页会把口径写在金额栏上 |
| `title` / `title_en` / `download_label` | 填写页标题和下载按钮 |
| `download_filename` | 可选；下载文件名，可用 `{project_name}` `{vendor_name}` `{payment_no}` |
| `drop_sheets` | 下载时删掉的工作表名（对照客户原件，不要猜） |
| `invoice_sheet` | 要填的那张表名；空则用第一张可见表 |
| `form.user_fields` | 供应商要填的抬头（网页 02 区）；`input: textarea` 出多行框 |
| `form.attachment_mode` | `lines` = 支持文件写进 Excel；缺省 `checklist` 只提醒不进表 |
| `writes` | `{from, cell, type}`：`from` 是填表数据键，`type` 为 `text` / `number` / `money` / `auto` |
| `vat` | 可选；`cells` + `format`，`{value}` 换成税率 |
| `claim_amount` | 可选；`name_cell` / `amount_cell` 或 `amount_cells` 写本次节点和金额 |
| `running_totals` | 可选；含税证书用的累计/剩余（`includes_this_claim` 时累计含本笔） |
| `support_file_cells` | 可选；支持文件每行写入这些格子 |
| `clear_on_adopt` | 可选；认模板时清空样例数字（ZIP 清空，图不动） |
| `previously_certified` | 可选；一个格子写以前请过的合计（不插行时用） |

`from` 常用键：`project_name`、`vendor_name`、`work_package`、`po_number`、`vendor_ref`、`contact_name`、`contact_mobile`、`office_phone`、`office_address`、`claim_node`、`claim_amount_excl_tax`、`contract_value_excl_tax`、`payment_no`、`period_count`、`nodes_overview`、`variations_to_date`。

客户单多出来的格子（开户行、发票抬头等）：在 `user_fields` 加一项，`writes` 里 `from` 用同一个 `key`。

## Agent 对照时

- 审批栏、签字日期：**不要**映射，留给人签。
- 公式格：**不要**覆盖。
- 金额口径跟客户模板走：模板写含税就填含税，写不含税就填不含税；填写页会标明。不要擅自改口径。
- **不要**为了对齐格子去重画 Excel。
- 版式不同的客户单一律按这张客户表起草对照，用 `engine: cells` 或 `insert_rows`。不要套别的业主的对照表。
