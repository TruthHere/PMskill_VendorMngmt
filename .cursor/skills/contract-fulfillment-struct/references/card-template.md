# 履约条件卡片（已迁出）

本规范已迁至辅助 Skill **`fulfillment-card`**：

- `.cursor/skills/fulfillment-card/SKILL.md`
- `.cursor/skills/fulfillment-card/references/card-template.md`
- `.cursor/skills/fulfillment-card/scripts/render_card.py`

**界面划分**：Skill 1 只提供干净 `card-data` → 调用 `fulfillment-card/render_card.py`；`履约条件卡片.html` 由 fulfillment-card 产出，`请款申请.html` 由 **payment-form** 产出（渲卡片时自动调用）。
