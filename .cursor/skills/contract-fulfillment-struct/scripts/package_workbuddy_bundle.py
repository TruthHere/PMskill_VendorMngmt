#!/usr/bin/env python3
"""Pack Skill 1 + runtime siblings for WorkBuddy smoke tests.

Skills live under ``.cursor/skills/``. The project-foundation **library**
lives under ``.cursor/lib/`` (not a Skill). Zip still places it as a sibling
folder so scripts can find it next to the skills.

Excludes secrets, evals, tests, and local junk.
"""

from __future__ import annotations

import fnmatch
import zipfile
from datetime import datetime
from pathlib import Path

SKILL1 = Path(__file__).resolve().parents[1]
SKILLS_ROOT = SKILL1.parent
CURSOR_ROOT = SKILLS_ROOT.parent
LIB_ROOT = CURSOR_ROOT / "lib"
REPO = CURSOR_ROOT.parent
OUT_DIR = REPO / "dist" / "workbuddy"

# Minimum set for process_email → Tracker / card-data → fulfillment-card.
# project-init included so WorkBuddy can seed a project without Cursor.
RUNTIME_SKILLS = (
    "skill-orchestration",
    "contract-fulfillment-struct",
    "fulfillment-card",
    "mail-inbox",
    "schedule-critical-nodes",
    "schedule-mpp-excel",
    "pdf-read",
    "project-init",
    "payment-request",
    "change-archive",
    "cashflow-forecast",
    "project-directory",
)
RUNTIME_LIBS = ("project-foundation",)

EXCLUDE_DIR_NAMES = {
    "__pycache__",
    "node_modules",
    "evals",
    "tests",
    ".git",
}
EXCLUDE_FILE_NAMES = {
    ".DS_Store",
    ".mailbox.secret",
    "mailbox-registry.json",
}
EXCLUDE_GLOBS = ("*.pyc", "*.secret", "*.pyo")


def skip(rel: Path) -> bool:
    if any(p in EXCLUDE_DIR_NAMES for p in rel.parts):
        return True
    if rel.name in EXCLUDE_FILE_NAMES:
        return True
    return any(fnmatch.fnmatch(rel.name, g) for g in EXCLUDE_GLOBS)


INSTALL_MD = """# Skill 1 运行时包 · WorkBuddy 安装

打包时间：{stamp}
用途：在 WorkBuddy 上先跑通「履约邮件 → Tracker / 包目录 / card-data / 履约卡片」。
企微深度联动、邮箱自动拉信可后接；本包先验证对话 + 脚本链路。

## 日常开发：这边改、那边测（推荐）

真源在仓库 `.cursor/skills/`（业务 Skill）和 `.cursor/lib/`（基建库）。改完后覆盖安装到 WorkBuddy，不必每次重打 zip：

```bash
cd "/path/to/PMskills"
python3 scripts/sync_skills_to_workbuddy.py --with-openpyxl
```

然后**重启 WorkBuddy / 新开对话**再测。Tracker xlsx 需要 `openpyxl`（见基建库 `project-foundation/requirements.txt`）。

## 为什么是一包多个文件夹？

脚本会在 **skills 根目录的邻居文件夹**里找基建库，例如：

`…/skills/contract-fulfillment-struct/scripts` → `…/skills/project-foundation/scripts`

`project-foundation` **不是 Skill**（技能列表里不应出现），但仍须和各 Skill **并列**放置，不能只装 `contract-fulfillment-struct` 一个。

本包包含：

| 目录 | 角色 |
|------|------|
| `contract-fulfillment-struct` | Skill 1 本体 |
| `project-foundation` | **共用库（不是 Skill）**：Tracker / 文件夹 / common |
| `fulfillment-card` | 履约卡片 HTML |
| `payment-form` | 请款申请 HTML + Excel |
| `mail-inbox` | 邮件分类（process_email 会引用） |
| `schedule-critical-nodes` | 建包时同步时间线（无进度源会 skip） |
| `pdf-read` | 读 PDF 正文（报价/合同；步骤 4 先读再抽节点） |
| `project-init` | Skill 0：先建项目再测 Skill 1 |

**未打入**（避免密钥/体积）：`.mailbox.secret`、`mailbox-registry.json`、evals、tests。

## 安装（推荐：解压到用户 skills）

1. 解压本 zip。
2. 把解压出的**各个文件夹**拷到（二选一，以你本机 WorkBuddy 为准）：
   - `~/.workbuddy/skills/`
   - 或项目下 `.workbuddy/skills/` / `.codebuddy/skills/`
3. 确认并列存在，例如：

```text
~/.workbuddy/skills/
  contract-fulfillment-struct/
  project-foundation/
  fulfillment-card/
  mail-inbox/
  schedule-critical-nodes/
  pdf-read/
  project-init/
```

4. 重启 WorkBuddy 或重新打开对话，确认技能列表里能看到「合同履约结构化」。
   **不应**把 `project-foundation` 当成一套可对话技能。

若企业后台**只允许上传单个 Skill zip**：请逐个把每个文件夹打成 zip 上传，或把整包解压到客户端本地 skills 目录（路径仍须并列）。

## 冒烟怎么说（对话）

先建项目（Skill 0）：

> 请用 project-init 在桌面建一个测试项目「WB-Smoke」，只做阶段 0，不要建采购包。

再测 Skill 1（把样例邮件路径换成你机器上的路径；包内有 samples）：

> 项目已初始化。请用 Skill 1 / process_email 处理这封 RFP 邮件：  
> `~/.workbuddy/skills/contract-fulfillment-struct/samples/input/` 下对应 `.eml`  
> 项目根是刚才的 WB-Smoke。

期望：Tracker 多一行、包文件夹、`07_往来文件` 有 `.eml`、`履约条件卡片.html` + `请款申请.html`。

无样例邮件时，可先在 Cursor 仓库跑：

```bash
python3 .cursor/skills/contract-fulfillment-struct/scripts/run_e2e_demo.py
```

再把 `samples/Sample-Project/` 拷到 WorkBuddy 工作区当已有项目继续测。

## 环境

- Python 3.10+（脚本用）
- Tracker xlsx：`openpyxl`（缺了可能只出 csv）
- 合同 OCR：`pdf-read` 按需配置 SoMark 等（见该 Skill 文档）

## 和企微的关系（当前）

本包**不含**企微 API / 在线表格同步。WorkBuddy 侧先验证：对话触发 → 本地落盘 Tracker/卡片是否正确；企微联动作为下一步单独接。
"""


def add_tree(zf: zipfile.ZipFile, skill_dir: Path, skill_name: str) -> int:
    n = 0
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(skill_dir)
        if skip(rel):
            continue
        arc = f"{skill_name}/{rel.as_posix()}"
        zf.write(path, arc)
        n += 1
    return n


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    zip_path = OUT_DIR / f"pm-skill1-workbuddy-runtime-{stamp}.zip"
    latest = OUT_DIR / "pm-skill1-workbuddy-runtime-latest.zip"
    install_path = OUT_DIR / "INSTALL-WorkBuddy.md"

    missing = [s for s in RUNTIME_SKILLS if not (SKILLS_ROOT / s / "SKILL.md").is_file()]
    if missing:
        raise SystemExit(f"Missing skills under {SKILLS_ROOT}: {missing}")
    missing_libs = [
        n for n in RUNTIME_LIBS if not (LIB_ROOT / n / "scripts" / "common.py").is_file()
    ]
    if missing_libs:
        raise SystemExit(f"Missing libs under {LIB_ROOT}: {missing_libs}")

    install_path.write_text(INSTALL_MD.format(stamp=stamp), encoding="utf-8")

    counts: dict[str, int] = {}
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("INSTALL-WorkBuddy.md", install_path.read_text(encoding="utf-8"))
        for name in RUNTIME_SKILLS:
            counts[name] = add_tree(zf, SKILLS_ROOT / name, name)
        for name in RUNTIME_LIBS:
            counts[name] = add_tree(zf, LIB_ROOT / name, name)

    # Stable alias for easy finding
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.write_bytes(zip_path.read_bytes())

    print(f"Wrote {zip_path}")
    print(f"Alias  {latest}")
    print(f"Install notes: {install_path}")
    for name, n in counts.items():
        print(f"  {name}: {n} files")
    print(f"Size: {zip_path.stat().st_size / 1024:.1f} KiB")


if __name__ == "__main__":
    main()
