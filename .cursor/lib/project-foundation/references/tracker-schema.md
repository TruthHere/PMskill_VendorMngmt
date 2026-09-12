# Tracker Schema（MVP · CSV）

MVP 使用项目根目录下的 **`{项目名称}_procurement_packages_status_tracker.csv`**（UTF-8 BOM），用 Excel / Numbers 可直接打开。编辑前请先关闭 Excel，避免文件锁。

文件第一行为 `# 最后更新,{ISO 时间}`；`项目背景.md` 与 `.skill/project.json` 中的 `tracker_last_updated` 同步。

## tracker.csv 表头

```
序号,采购包名称,供应商名称,供应商简称,对接人邮箱,采购包类型,金额不含税,金额含税,金额备注,交期摘要,已请金额,待请款金额,下一付款节点,请款进度,RFP 发出,技术方案已确认,商务报价已确认,PO 已发起,已结算,卡片路径,文件夹路径
```

同目录自动生成 **`*.xlsx`**（合并「状态」表头、配色、筛选、冻结窗格），**PM 日常请打开 xlsx**；csv 供脚本读写。

### CSV 双行表头

CSV 无法合并单元格，用**分组行 + 列名行**表达「请款」「状态」大列：

```csv
# 最后更新,2026-07-19T…
,,,,,,,,,,请款,,,,状态,,,,,
序号,采购包名称,…,已请金额,待请款金额,下一付款节点,请款进度,RFP 发出,…
01,BMS,…
```

脚本读入时会自动跳过分组行。

| 列名 | 内部键 | 说明 |
|------|--------|------|
| 序号 | `seq` | 与文件夹前缀一致（如 `01_…` → `01`） |
| 采购包名称 | `package_name` | 从邮件识别 |
| 供应商名称 | `supplier_name` | 全称 |
| 供应商简称 | `supplier_short` | 文件夹命名 |
| 对接人邮箱 | `contact_email` | **To / Cc / From** 中匹配供应商域名的地址，多个用 `; ` 分隔 |
| 采购包类型 | `package_type` | `供应` / `供装` / `顾问` / `总包` |
| 金额不含税 | `amount_excl_tax` | **纯数字**（如 `85043243.04`） |
| 金额含税 | `amount_incl_tax` | **纯数字** |
| 金额备注 | `amount_remark` | 不含税/含税字段中的说明（如 `不含暂定工程`） |
| 交期摘要 | `delivery_summary` | 一句话 |
| **已请金额** | `claimed_amount_excl_tax` | 请款章节；**不含税**累计。仅**客户批复**后回写 |
| **待请款金额** | `remaining_claim_amount_excl_tax` | 请款章节；不含税合同额 − 已请金额 |
| 下一付款节点 | `next_payment_node` | 请款章节；下一笔待请的节点名 |
| **请款进度** | `payment_progress` | 请款章节；当前在办这一笔的状态人话（如 `已发QS核对 · 到货 / Delivery`）。无在办写 **`无在办`**。只显示当前状态，不记各步时间 |

请款四列合称「请款章节」：**请款状态的唯一真相**（不另开 payment_ledger）。进度每推一步都回写；已请/待请只在客户批复后变。旧表没有「请款进度」时读入为空，下次 Skill 2 回写会补上。`03_请款记录/` 只存邮件/Excel/附件档案。
| **RFP 发出** | `ts_rfp_issued` | 里程碑完成日期 `YYYY-MM-DD` |
| **技术方案已确认** | `ts_tech_confirmed` | 同上 |
| **商务报价已确认** | `ts_quote_confirmed` | 同上 |
| **PO 已发起** | `ts_po_issued` | 同上 |
| **已结算** | `ts_settled` | 同上 |
| 卡片路径 | `card_path` | 履约条件卡片.html |
| 文件夹路径 | `folder_path` | 采购包根目录 |

以上五列里程碑 **collectively 表示「状态」**：有完成时间戳即已到达该节点，空白即未完成。**不再单独维护「状态」下拉列**。

在 Excel 中可将这五列合并单元格，上方加一行分组标题「状态」。

旧列 `总金额` 读入时映射到 `金额不含税`；旧列 `状态`、`时间_*` 读入时自动迁移到新里程碑列；保存只写新表头。

## 金额与税率

- 展示格式统一：`¥12,345.67`（CNY/RMB）或 `USD 12,345.67`
- **两列都要**：不含税 / 含税
- **必须从报价附件同步抓取**（Raise PO / 合同步骤）：
  - 扫描本次附件 + `01_合同报价/` 内已有 `.xls`/`.xlsx`/`.csv`（`.xls` 需 `xlrd`，见 `requirements.txt`）
  - 识别 `Amount before VAT` / `Include.VAT`、以及 `Global Total … w/o Tax` / `With Tax` / `Tax（9%）` 等表头列（取合计行，非明细行）
  - **附件为准**写入 Tracker；正文只补附件缺的一侧（正文常从附件摘录，可能抄错）
  - 附件与正文数字不一致 → 仍写附件，并 `pending`（`amount_mismatch_body_vs_quote`）
  - 有报价附件但抽不出金额 → `pending`（`quote_amount_unparsed`）；Agent 应打开附件理解后再填
- 只有金额、税率不明 → 先写已知侧，并进 `pending`（`tax_rate_uncertain`）向 PM 确认

## 里程碑与邮件步骤

```
RFP 发出 → 技术方案已确认 → 商务报价已确认 → PO 已发起 → 已结算
```

| 触发步骤 | 写入里程碑列 |
|----------|--------------|
| 步骤 1 RFP | `RFP 发出` |
| 步骤 2 技术确认 | `技术方案已确认` |
| 步骤 3 Raise PO | `商务报价已确认` + `PO 已发起`（PO 隐含报价已确认，若报价列空则同时写入） |
| 结算完成 | `已结算` |

时间优先取邮件 `Date` 头，转 CST ISO（如 `2026-07-07T15:49:00+08:00`）。同一列首次有值后不覆盖。

## 邮件归档规则

- 凡落入采购包的 AI 邮箱邮件：整封以 **`.eml`** 存入该包 `07_往来文件/`
- `01_合同报价/`：**仅**报价/合同类附件（pdf/doc/xls 等）；签名动图、`image001.gif` 等无关图不入库

## project.json · mailbox（可选）

见 `references/mailbox-setup.md`。**不要**把测试邮箱绑到 `samples/`。

## pending.json

低置信度 / 税率不明 / 付款未解析等。**唯一写入口**：基建库 `pending_store.py`（`add_pending` / `close_pending`）。

每条必须有：

| 字段 | 说明 |
|------|------|
| `skill` | 是哪个 Skill 的（如 `change-archive`）。没这字段不能新写 |
| `pending_id` | 脚本生成 |
| `status` | `open` / `confirmed` / `cancelled` |
| `reason` | 待确认原因码 |

每个 Skill **只能关自己的** `pending_id`。进度节点自己的 pending 在 `schedule.json`，禁止写进这份。详见 `skill-orchestration`。

## card-data.json（每包）

与 HTML 卡片对应，供 **fulfillment-card** `render_card.py` 增量合并。**HTML 必须由 fulfillment-card 从 `assets/fulfillment-card.html` 渲染**；格式规则见 `fulfillment-card/references/card-template.md`。

必填展示字段（写入 JSON，由模板映射到 HTML）：

| 键 | 说明 |
|----|------|
| `supplier_name` | 页眉**主标题** |
| `package_name` | 页眉副标题「采购包 …」 |
| `package_type_label` | 类型徽章 |
| `payment_nodes` | 付款节点数组；表格含请款附件列 |
| `change_items` | **已废弃**。变更只在 Change Log；渲染忽略此字段，Skill 3 不再写入 |
| `constraint_clauses` | 约束条款文本；**仅总包**渲染到 HTML |

