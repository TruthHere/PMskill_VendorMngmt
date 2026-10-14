# 关键节点码表（行业共识 × 包类型）

本文件是 `critical-nodes` 的节点语义真源。**Agent 推理与下游 Skill** 按 `node_code` 对齐，勿随意改码；新增节点时追加，不复用旧码。

## 包类型（与 Skill 1 一致）

| `package_type` | 展示名 | 典型例子 |
|----------------|--------|----------|
| `供应` | 纯供应 | 石材、灯具供应、配电箱供应 |
| `供装` | 供应+安装 | 木饰面供装、玻璃隔断、IT cabling、BMS |
| `顾问` | 顾问服务 | 灯光顾问、机电顾问 |
| `总包` | 总包 | 室内装修总承包 |

## 谁挂哪些节点

| 对象 | 挂什么 |
|------|--------|
| **各采购包** | 只挂该包**请款相关**关键节点（到货/安装/调试/验收等） |
| **总包** | 整盘公共节点（许可证、隐蔽验收、竣工/客户验收等）；**不要**再单独搞抽象「项目级 / `_project`」行 |

旧数据若仍用 `package_name=_project`，时间线兼容显示为「项目锚点（旧）」；新分析请写到 `package_name=总包`。

## 总包（`总包`）

关注点因项目而异，**不是**固定四件套。常见例如：

| 示例 | 典型计划用语 | 建议 `node_code` |
|------|--------------|------------------|
| 施工许可证 | Obtain permit / 施工许可证 | `gc_milestone`（名称保留原文） |
| 墙体隐蔽 | Wall Cover-Up / 隔墙隐蔽 | `gc_milestone` |
| 天花隐蔽 | Ceiling Cover-Up / 吊顶隐蔽 | `gc_milestone` |
| 开工 | Commencement / 开工 | `project_start` |
| 竣工 | Practical Completion / 竣工批文 | `project_completion` |
| 客户验收 / 移交 | Client final acceptance / Handover | `project_handover` 或 `gc_milestone` |

计划叫法乱时优先 `gc_milestone`，`name` / `basis` 写原文。  
本 Skill **不**替代合同附件产值核验 / 请款核定。

## 纯供应（`供应`）

顺序（不可颠倒）：

| 顺序 | node_code | 中文 | 英文 | 默认是否展开 |
|------|-----------|------|------|--------------|
| 1 | `po_confirm` | 下单确认 | PO Confirmed | 可选 |
| 2 | `fat` | 出厂 / 厂验 | FAT / Ex-works | 可选（设备类） |
| 3 | `shipment` | 发运 | Shipment | 可选 |
| 4 | `delivery` | 到货验收 | Delivery / Arrival Acceptance | ✅ |
| 5 | `commissioning` | 调试 | Commissioning | 可选（计划有功能测试/调试时展开） |
| 6 | `warranty_start` | 质保起算 | Warranty Start | 可选 |

MVP 默认必推：`delivery`。其余在原计划命中或 PM 指定请款节点时再展开。

## 供应+安装（`供装`）

| 顺序 | node_code | 中文 | 英文 | 默认是否展开 |
|------|-----------|------|------|--------------|
| 1 | `po_confirm` | 下单确认 | PO Confirmed | 可选 |
| 2 | `fat` | 出厂 / 厂验 | FAT | 可选 |
| 3 | `shipment` | 发运 | Shipment | 可选 |
| 4 | `delivery` | 到货验收 | Delivery | ✅ |
| 5 | `site_access` | 进场 | Site Access / Mobilization | ✅ |
| 6 | `install_complete` | 安装完成 | Installation Complete | ✅ |
| 7 | `commissioning` | 调试 | Commissioning | 可选 |
| 8 | `prelim_accept` | 初步验收 | Preliminary Acceptance | ✅ |
| 9 | `final_accept` | 最终验收 | Final Acceptance | ✅ |
| 10 | `warranty_start` | 质保起算 | Warranty Start | 可选 |

MVP 默认必推：`delivery` → `site_access` → `install_complete` → `prelim_accept` → `final_accept`。  
**以该包请款节点为准裁剪**：PM 只要求部分节点时，不要为填满模板硬推。

## 顾问（`顾问`）

| 顺序 | node_code | 中文 | 英文 | 默认是否展开 |
|------|-----------|------|------|--------------|
| 1 | `contract_sign` | 签约 | Contract Signed | 可选 |
| 2 | `concept` | 方案 | Concept / Scheme | ✅ |
| 3 | `detail_deliverable` | 施工图 / 成果交付 | Detail Deliverable | ✅ |
| 4 | `site_support` | 现场配合 | Site Support | 可选 |
| 5 | `deliverable_accept` | 成果验收 | Deliverable Acceptance | ✅ |

## 与付款语义对齐

下游履约卡片 / 请款可按下列映射取节点，**请款日期取该节点的 `window_end`（完成日）**：

| 付款语义关键词 | 优先 node_code |
|----------------|----------------|
| 预付 / advance | `po_confirm` 或 `project_start` |
| 到货 / delivery | `delivery` |
| 安装 / install | `install_complete` / `commissioning` |
| 验收 / accept / 尾款 | `prelim_accept` / `final_accept` / `deliverable_accept` / `project_handover` |
| 质保 / retention | `warranty_start` |

呈现与旬粒度见 `presentation.md`。

### 包级验收 vs 总包/客户验收（Agent 必守）

若计划**没有**该包独立验收行：

- 包的「验收」请款完成时点，**默认对齐总包/客户验收前后**（如 Client final acceptance、业主初验）
- **不要**在安装刚完成就提前一两个月当作验收完成
- 与项目验收完成日相差不宜超过约一个月；吃不准 → `needs_confirm` / `pending`
