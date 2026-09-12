---
name: project-directory
description: >-
  项目通讯录（Skill 5 · Project Directory · project-directory）。用企微群消息（或填写页）
  收集供应商对接人的姓名、Title、手机、邮箱，汇总成一张 Excel。不走邮箱。
  务必在用户提到 Project Directory、项目通讯录、供应商联系方式、对接人信息、
  联系人收集、通讯录、联系表、群里收联系人、填写页时使用。
---

# 项目通讯录（Skill 5 · Project Directory）

一句话：把填空模板发到**项目群**，供应商在群里回；收齐后合成**一张项目联系表**。

**不走邮箱。** 合同/RFP/请款可以继续用邮件；通讯录这种「填四个格子」的事放群里更快。

**全局原则**：先理解再处理（见 `skill-orchestration`）——群回复先看清是哪家、填了谁，再写入表；抽不出就问人，禁止瞎填手机号。

## 人话流程

1. 你说「收集联系方式 / 发 Project Directory」
2. 系统写出两样，给你复制：
   - **群消息**：一段固定填空，直接发到项目群
   - **填写页.html**：丢进群文件；对方手机打开、填完点「复制回群」
3. 供应商按同一格式回群
4. 你把群里的回复贴过来（或 WorkBuddy 在群里看到 `[PDIR]` 回复）→ 并进 `{项目名}_项目通讯录.xlsx`

## 做什么 / 不做什么

| 做 | 不做 |
|----|------|
| 写群消息 + 填写页 | 发邮件 / SMTP / 走 mail-inbox |
| 解析群回复或填写页 JSON，写入通讯录 | 改 Tracker、请款、变更 |
| 对不上哪家 → pending 问你 | 每次建包偷偷往群里刷 |

前置：项目已初始化。有采购包更好（群消息会带名单）；没有也可以让对方自己写包名。

## 主路径

生成群消息和填写页：

```bash
python3 .cursor/skills/project-directory/scripts/compose_group_post.py \
  --project-root "/path/to/project"
```

你已经发到群里之后：

```bash
python3 .cursor/skills/project-directory/scripts/compose_group_post.py \
  --project-root "/path/to/project" \
  --mark-posted
```

收录群回复（把对方发的那段贴进来）：

```bash
python3 .cursor/skills/project-directory/scripts/ingest_directory_reply.py \
  --project-root "/path/to/project" \
  --text "[PDIR]
采购包：BMS
姓名 / Name：王工
Title：项目经理
手机 / Mobile：13800138000
邮箱 / Email：wang@vendor.com
"
```

或 `--text-file` / `--json-file`（填写页导出的回执）。

只刷 Excel：

```bash
python3 .cursor/skills/project-directory/scripts/write_directory_xlsx.py \
  --project-root "/path/to/project"
```

## 产物

| 文件 | 给谁看 |
|------|--------|
| `{项目名}_项目通讯录.xlsx`（项目根） | **你日常打开这一张** |
| `项目档案/05_项目通讯录/群消息.txt` | 复制发到企微群 |
| `项目档案/05_项目通讯录/填写页.html` | 丢进群文件，当填写链接用 |
| `.skill/directory.json` | 机器底账 |

Excel 两张表：`项目通讯录`（一人一行）、`收集进度`（待发群消息 / 已发群待回 / 已收录）。

口径与文案：`references/directory-schema.md`、`references/group-message.md`、`references/xlsx-layout.md`。

## 和别的 Skill

| 对方 | 关系 |
|------|------|
| Tracker（Skill 1） | **只读**采购包名单，写进群消息；**不写回** Tracker |
| mail-inbox | **不参与**。通讯录回执不要进邮箱分拣 |
| Skill 0 | 没建项就先初始化 |
| Skill 2 / 3 / 4 | 无关 |

WorkBuddy 若已经在项目群里：把 `群消息.txt` 发到该群即可，对方回 `[PDIR]` 后按 ingest 收录。现在还没有自动监听群聊时，**你把回复贴给 Agent** 就行。

## Agent 清单

- [ ] 用户要的是通讯录，不是履约/请款？
- [ ] 是否已生成群消息，并把正文给用户复制（同时告诉填写页在哪）？
- [ ] 用户说「已发到群」后是否 `--mark-posted`？
- [ ] 贴过来的群回复是否抽出姓名/Title/手机/邮箱？抽不全是否问人而不是空写？
- [ ] 是否已写出项目根那张 xlsx？
- [ ] 是否**未**发邮件、**未**改 Tracker / ledger / Change Log？

## 冒烟

```bash
python3 .cursor/skills/project-directory/scripts/smoke_skill5.py
```
