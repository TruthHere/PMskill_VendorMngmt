# 履约条件卡片模板规范（强制）

模板文件：`assets/fulfillment-card.html`  
渲染脚本：`scripts/render_card.py`（读 `card-data.json` → 写 `履约条件卡片.html`）

**Agent 生成或更新任何履约卡片时，必须先读本文并只通过 `render_card.py` 出 HTML。**

## 禁止事项

- ❌ 直接编辑 `履约条件卡片.html`
- ❌ 复制旧包 HTML 当作新包模板
- ❌ 页眉用 `package_name` 作主标题（历史错误格式）
- ❌ 在正文单独放「数据来源」块（须在页脚）
- ❌ 跳过 `render_card.py` 只改 `card-data.json` 而不重渲染
- ❌ 忽略 `quality_warnings`（烂数据可以出卡，但必须提示 PM）

## 数据质量提醒（软门禁）

格式错误 → **拒出卡**。数据不清 → **仍出卡**，同时：

1. `card-data.json` 写入 `quality_ok` / `quality_warnings[]`
2. 卡片**最上方**（页眉之前）渲染「数据不够清晰（N 项）」横幅（`{{quality_banner_html}}`）
3. stdout JSON 带回同样字段

**不**写入 `pending.json`。检查项见 `scripts/card_quality.py`。

## 页眉（必遵）


| 元素             | 字段                   | 规则                          |
| -------------- | -------------------- | --------------------------- |
| 类型徽章           | `package_type_label` | 如「纯供应」「总包」                  |
| **主标题 `<h1>`** | `**supplier_name**`  | **供应商/承包商全称**，最大字号、加粗       |
| **副标题**        | `**package_name`**   | 文案：`{package_name}`，字号小于主标题 |
| 右上角            | 固定                   | 「发起请款」链到同包 `请款申请.html` |


模板标记（用于校验）：`card-title` 内必须是 `{{supplier_name}}`；副标题含 `class="package-name"`。

## 字段区（八格）


| 字段 | `card-data` 键 |
| --- | --- |
| 供应商 | `supplier_name` |
| 项目 | `project_name` |
| 合同/报价单编号 | `contract_or_quote_no` |
| 签约/报价日期 | `contract_or_quote_date` |
| 对接人邮箱 | `contact_email` |
| 总金额 | `total_amount`（须标注含税/不含税） |
| 供应/服务范围 | `scope_summary` |
| 交期/服务周期 | `delivery_schedule` |


## 付款节点

由 `render_card.py` 根据 `payment_nodes[]` 渲染；**禁止在 HTML 里手写节点块**。

### 单节点 JSON 字段


| 键           | 说明                     |
| ----------- | ---------------------- |
| `name`      | 节点名（如 `到货 / Delivery`） |
| `pct`       | 比例                     |
| `condition` | 触发条件（宜短）               |
| `milestone` | 可选；截止日或附件 B 摘要         |
| `schedule_window` | 可选；与项目进度计划对齐的时间区间 |
| `source`    | 来源                     |


### 总包 / 附件 B

合同正文仅写「施工进度 N」时，须经 `pdf-read` 读全文，定位 `## 附件 B`，把 8 个「施工进度目标」写入 `condition`/`milestone`。

## 验收标准 / 约束条款 / 页脚

- `acceptance_items[]` → 勾选列表
- `constraint_clauses` → 正文**红色浅底框**（仅总包）
- `data_sources` + 免责声明 → **仅页脚**（`footer-meta`）

## 标准工作流

```
1. Skill 1（或其它业务 Skill）更新 card-data.json（或 render_card.py --patch）
2. fulfillment-card/render_card.py 合并 patch → 履约条件卡片.html →（自动）payment-form 刷请款申请.html
```

```bash
python3 .cursor/skills/fulfillment-card/scripts/render_card.py \
  --package-dir "/path/to/package_folder" \
  --patch '{"supplier_name":"Modular Space","package_name":"Carpet_Rubber_floor", …}'
```

仅刷新两页 HTML（数据不变）：

```bash
python3 .cursor/skills/fulfillment-card/scripts/render_card.py \
  --package-dir "/path/to/package_folder" \
  --patch '{}'
```

## 模板变更后

修改 `assets/fulfillment-card.html` 后，对项目内所有含 `card-data.json` 的包执行 `--patch '{}'` 批量重渲染。请款页模板在 `payment-form`，改那边后可只跑 `payment-form/scripts/sync_claim_form.py`。
