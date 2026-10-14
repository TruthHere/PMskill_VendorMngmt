# 合同 PDF 提取管线（系统内 · 先 read-pdf 再 Skill 1）

**服从**上级 [`../SKILL.md`](../SKILL.md)。  
Skill 1 步骤 4a：**禁止**默认全本渲图；读 PDF **必须**先走 `read-pdf`（只出正文）。付款节点由 **Skill 1** 从正文抽取，不在 read-pdf 里做。

> 用户只要「读这份 PDF / OCR」、未提履约 → 只跑 `read-pdf`，不要擅自写卡片/Tracker。  
> 本项目读文字 **不要** 用全局 `pdf` 伴侣。

## 架构（系统内）

```text
合同 / 报价 PDF
  → read-pdf/scripts/read_pdf.py
       ├─ 文本型 → 本地 extract
       ├─ 扫描/复杂 → SoMark CLI
       └─ 长文档 → SoMark --async --wait
  → read.json（text / markdown / …，无 payment_nodes）
  → Skill 1 extract_contract_pdf.py --read-json read.json
       → payment_nodes 候选
  → PM 确认 → vendor-card render / update_tracker
```

权威读 PDF 文档：`.cursor/skills/read-pdf/SKILL.md`  
付款节点启发式：`.cursor/skills/po-flow/scripts/extract_contract_pdf.py`

## 强制命令

```bash
python3 .cursor/skills/read-pdf/scripts/read_pdf.py \
  --pdf "/path/to/contract.pdf" \
  --project-root "/path/to/project" \
  --out "/path/to/contract-read.json"

python3 .cursor/skills/po-flow/scripts/extract_contract_pdf.py \
  --read-json "/path/to/contract-read.json" \
  --out "/path/to/payment-candidates.json"
```

| 结果 | 动作 |
|------|------|
| `read-pdf` 的 `source: local`，有文本 | Skill 1 精炼 `payment_nodes`，来源 `合同提取` |
| `read-pdf` 的 `source: somark` | 用 Markdown 交给 Skill 1 精炼节点 |
| `error` / SoMark 不可用 | 优先页识图；不足则占位 + PM 手填 |

## 速度约束

- 禁止全本渲图
- 总包滚动款归 Skill 2
- `payment_nodes` 须 PM 确认

## 职责划分

- **read-pdf**：分类 + 读出正文。不抽付款节点。
- **Skill 1 `extract_contract_pdf.py`**：吃 read-pdf 的 JSON，出付款节点候选。入口始终是先 `read_pdf.py`。
