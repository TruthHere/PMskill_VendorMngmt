#!/usr/bin/env python3
"""Build docs/采购包技能介绍.html from the live SKILL.md files."""

import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".cursor" / "skills"
OUT = ROOT / "docs" / "采购包技能介绍.html"

INTROS = [
    {
        "id": "new-project",
        "kind": "station",
        "kind_label": "工位",
        "mark": "0",
        "title": "项目初始化",
        "lead": "先把空项目立起来。采购包从下一站才开始。",
        "mode": "对话里建，不吃待处理邮件",
        "use": "在对话里说「新建项目」。它把没给的必填问完，再建立文件夹。像建项的邮件留在待处理里，不会从那夹自动建项目。",
        "does": "你说要新建项目，它先把没给的必填一次问完：项目名称、编号、类型、地址、甲方、项目经理、文件夹放哪、用什么币、金额含不含税。齐了才建文件夹。你能看见的是项目背景、一张空的采购包状态表、进度计划文件夹、待处理邮件。这次要是顺便给了进度计划，或一份客户请款单（只要 .xlsx），同一回合接着办。",
        "when": "你说新建项目、项目初始化、阶段 0、文件夹放哪。采购包、请款入账、变更都不要在这一站做。",
        "questions": [
            ("必填还差几项，能先建个空壳吗？", "不能。缺一项就不跑，也不先建文件夹。"),
            ("币种我没说，按人民币含税行不行？", "不行。币种和含不含税用你的原话，没有默认值。"),
            ("要绑项目邮箱吗？", "这版不问邮箱，也不连邮箱。邮件是你自己另存进「待处理邮件」。"),
            ("文件夹里已经有一个项目了？", "先问你：接着用这个，还是换一个空文件夹。接着用就不要再跑建项。"),
        ],
        "works": [
            "看得到项目背景、采购包状态表、进度计划文件夹、待处理邮件。",
            "没有空采购包，也没有「已处理邮件」。",
            "对人有一份关键节点时间线。没进度的话，先是一张空壳。",
            "给了 .xlsx 请款单，模板已经认过。没给，你会听到一句：请款单生成尚未启用。",
        ],
    },
    {
        "id": "po-flow",
        "kind": "station",
        "kind_label": "工位",
        "mark": "1",
        "title": "合同履约",
        "lead": "从建包起。把履约邮件收成状态表、包文件夹和一张能打开的卡片。",
        "mode": "邮件分到就办，不用点名",
        "use": "履约邮件放进「待处理邮件」，说「处理待处理邮件」。分到这一站就建包、归档、出卡片。你要改已经建好的某一包，在对话里指出那个包。",
        "does": "它吃的是履约这件事：RFP、技术确认、Raise PO、付款条件、合同。结果是采购包状态表更新、包文件夹归档、一份干净的卡片数据，然后交给履约卡片去出页面。页面它自己不画。请款入账和变更它也不办。",
        "when": "你提到采购包、RFP、技术确认、Raise PO、付款条件、履约邮件、状态表。项目还没建，先走上一站。请款进度和变更台账不要塞进这一站。",
        "questions": [
            ("回信主题里引用了原来的 RFP，会再建一个包吗？", "不该建。只看这封回信最新一段在办什么。分类器把引用正文判成高置信，也不算数。"),
            ("包建好了，到货日是不是脚本写好了？", "没有。脚本最多重画项目里那一份时间线。这一回合还要把这个新包的节点补上。邮件里没有到货日，就标待确认。"),
            ("邮件正文和报价单金额不一致？", "以报价附件为准。对不上就挂起问你，不挑一个悄悄写死。"),
            ("图纸只给了网盘链接？", "包里的图纸文件夹要留一份指针，写上链接和密码。不要登网盘去下。"),
        ],
        "works": [
            "状态表多了这个包，文件夹在，里程碑盖了该盖的时间。",
            "履约条件卡片能打开。有请款单模板的话，请款申请页也一起刷好了。",
            "吃不准的在待确认里，你能看见问的是哪一项。",
        ],
    },
    {
        "id": "payment-flow",
        "kind": "station",
        "kind_label": "工位",
        "mark": "2",
        "title": "请款",
        "lead": "只盯每一包的下一笔。客户批复之前，已请金额不动。",
        "mode": "邮件分到就办，不用点名",
        "use": "请款邮件放进「待处理邮件」，说处理。分到这一站就推进请款五步。你也可以在对话里说扫一遍快到期的包，或把客户批复记上。改请款页、下载 Excel 不走这一站。",
        "does": "它按关键节点的完成日，提前大约两周提醒你：这一包下一笔该请了。请款走五步：供应商来请、发给 QS、QS 确认金额、发给客户、客户批复。五步都记在采购包状态表的「请款进度」上。只有客户批复，才把这笔加进已请金额，并切到下一节点。邮件和 Excel 放进这个包的请款记录文件夹，不另开一本账。",
        "when": "你说请款提醒、请款进度、下一笔待请、QS 核对、客户批复、PAYMENT NO。要改请款页、要下载客户那张 Excel，走请款申请页那一份，不要用这一份。",
        "questions": [
            ("供应商请款函来了，已请金额要加吗？", "不加。进度记成已收到。已请金额等客户批复。"),
            ("五步没走完，直接记批复？", "脚本拦住，记成待确认。你明确说这是补录，才允许跳。"),
            ("请款页是谁做的？", "请款申请页那份技能。这一份只消费那一页，用来推进状态和归档。"),
            ("账记在哪？", "只记采购包状态表那一行。请款记录文件夹是档案柜。"),
        ],
        "works": [
            "状态表上的请款进度，对得上五步里的某一步。",
            "客户还没批复，已请金额没有变。",
            "这封邮件和附件在该包的请款记录里。",
        ],
    },
    {
        "id": "change-flow",
        "kind": "station",
        "kind_label": "工位",
        "mark": "3",
        "title": "变更存档",
        "lead": "变更单独一本台账。不定价，也不去改采购包那一行。",
        "mode": "邮件分到就办，不用点名",
        "use": "变更邮件放进「待处理邮件」，说处理。分到这一站就写入变更台账并归档。标成已取消要你改台账，邮件不会自动改成取消。",
        "does": "它把变更邮件写成变更台账，并把邮件、图纸按规则归档。状态顺着走：COD、PMI、技术审核、技术确认、商务确认、商务金额确认、Change PO。你也可以手把某一行改成已取消。金额只照抄，不含税。它不帮你核定该值多少钱。",
        "when": "你提到变更、COD、PMI、技术文件审核、商务金额、CP Confirm、Change PO、变更序号、变更洽商。",
        "questions": [
            ("帮我算这笔变更多少钱？", "不算。预估和最终金额都是原样抄进台账，而且是不含税。"),
            ("变更确认了，采购包状态表要改吗？", "不改。履约卡片也不写。请款和现金流自己来读这本台账。"),
            ("技术还没确认，商务邮件先到了？", "挂起问你，不跳级硬推。"),
            ("这行我手改成已取消了？", "之后的邮件还可以归档，但状态和金额不再往前推。"),
        ],
        "works": [
            "变更台账有这一行，主键是变更序号加采购包名称。",
            "对应那一列盖了时间戳，旧戳没被盖掉。",
            "邮件在变更洽商和往来文件里。图纸进了变更洽商，也进了图纸文件夹。",
            "采购包状态表没被这封变更邮件改动。",
        ],
    },
    {
        "id": "mail-inbox",
        "kind": "entry",
        "kind_label": "入口",
        "mark": "收",
        "title": "待处理邮件",
        "lead": "整封邮件放进文件夹，说一声处理。它只负责分对站。",
        "mode": "你放进夹，说一声处理",
        "use": "把整封 .eml，或 Outlook 另存的 .msg，放进项目根的「待处理邮件」，然后说「处理待处理邮件」。.msg 会先转成标准邮件再认。它认完信，交给履约、请款或变更。这三站不用你再点名。看不准的留下问你，不改账。",
        "does": "你把整封 .eml 或 Outlook 的 .msg 放进项目根的「待处理邮件」，然后说处理待处理邮件。.msg 先转成标准邮件。它扫描、分类，能确定的交给履约、请款或变更。办成的，归档进采购包对应文件夹，并把待处理里的原件拿走。它自己不改状态表，不写变更台账，不记已请金额。",
        "when": "你说处理待处理邮件、把这封信分给履约 / 请款 / 变更。建项不要从这夹里做。",
        "questions": [
            ("要连邮箱自动收吗？", "这版不要。你自己另存 .eml，或从 Outlook 另存 .msg，放进去。"),
            ("看不准，或者是回信？", "原件留在待处理里。回信先读最新一段，跟你对上意图，再交出去。"),
            ("像一封新建项目的邮件？", "留下。告诉你回到对话里建项，不在这夹里建。"),
            ("办完的放哪？", "进采购包里该去的文件夹。不另建「已处理邮件」。"),
        ],
        "works": [
            "你听到一份清单：办成了什么、哪封是重复的、哪封还要你拍板。",
            "办成的原件已经不在待处理里。",
            "看不准的还在，账没有被悄悄改掉。",
        ],
    },
    {
        "id": "vendor-card",
        "kind": "craft",
        "kind_label": "手艺",
        "mark": "卡",
        "title": "履约卡片",
        "lead": "把已经写好的卡片数据画成一页。画完顺手刷请款页。",
        "mode": "可以单独叫",
        "use": "你说重画某个采购包的履约卡片，就只画这一页。平时不用叫。建包或改了卡片数据，履约会喊它，喊完请款页也刷了。",
        "does": "它读这个包的卡片数据，写出同包的履约条件卡片。写完自动去刷请款申请页。项目还没认过客户请款单模板，请款页就写成「尚未启用」，不用别的项目的样例表顶上。数据看着可疑，卡片仍然出来，顶栏必须提醒你。它不收邮件，不改状态表，不办请款入账，不记变更。",
        "when": "你要改履约卡片长什么样。平时不用点名：建包、改卡片数据之后，由履约那一站喊它。数字抽得对不对，回到履约那一站。请款页的版式，去请款申请页那一站。",
        "questions": [
            ("卡片刷完，还要再刷一遍请款页吗？", "不用。出卡片的时候已经刷过。再刷一遍就是做两遍。"),
            ("没有客户请款单模板？", "请款页是未启用提醒。你会听到那句：请款单生成尚未启用。"),
            ("顶上的质量提醒会进待确认清单吗？", "不会。它只留在卡片顶栏。"),
        ],
        "works": [
            "这个包里有履约条件卡片.html，打开就是刚写入的数据。",
            "请款申请.html 要么是填写页，要么是未启用页。两种都算刷完。",
        ],
    },
    {
        "id": "payment-sheet",
        "kind": "craft",
        "kind_label": "手艺",
        "mark": "单",
        "title": "请款申请页",
        "lead": "用客户原来那张请款单。认格子，再填。不重画一张。",
        "mode": "可以单独叫",
        "use": "你交来这个项目的客户请款单，或只要重刷、下载请款页，就只做这件事。出履约卡片时会被自动喊去刷页。已请金额仍归请款那一站。",
        "does": "换项目、换业主时，拿客户现成的请款单来认：哪些格子要人填，哪些版式必须留着。认的时候跟你对一遍。之后每个采购包有一页请款申请，打开就能把本包信息填进那张原表，下载出来版式还是客户的。图、表头、合并格都留着。本次请多少由供应商填，它不按比例代算，也不把已请金额展示在网页上。",
        "when": "你交出客户请款单、要换模板、要下载请款 Excel、要改请款申请那一页。建项时如果同时给了 .xlsx，同一回合就认模板，那时还没有采购包，先不要刷页。入账仍归请款那一站。",
        "questions": [
            ("客户给的是 .xls 或 Word？", "停。目前只收 .xlsx。请款单生成仍未启用，不去转换、不去重画。"),
            ("还没认过模板，能先用技能里的样例吗？", "不能。没有这个项目自己的客户请款单，就保持未启用。"),
            ("网页上为什么没有已请金额？", "已请在采购包状态表，归请款那一站。这一页不展示。"),
            ("格子对不上别的项目的请款单？", "只认这个项目的对照表。不按业主品牌去猜格子。"),
        ],
        "works": [
            "项目里存着这份客户模板和一份对照表。",
            "采购包里能打开请款申请.html，下载下来还是客户那张表的样子。",
            "合同额从状态表的不含税金额带出。本次金额空着等填。",
        ],
    },
    {
        "id": "read-pdf",
        "kind": "craft",
        "kind_label": "手艺",
        "mark": "读",
        "title": "读 PDF",
        "lead": "把报价单、合同、扫描件读成文字。读完就停。",
        "mode": "可以单独叫",
        "use": "你说帮我看这份 PDF，交出来的是正文，到此为止。合同要写进采购包时，由履约在同一回合喊它，你不用先点这份的名。",
        "does": "先判断这份 PDF 是文字版还是扫描件，再选本地抽字或认字，交给你一份统一的正文。它不抽付款节点，不写状态表，不出卡片。合同要进采购包时，正文读完交给履约那一站去抽付款节点，你确认后再写入。",
        "when": "你说帮我看这份 PDF、读一下报价单、合同、扫描件认字。你只想看内容，就停在正文，不要自动去建包或改账。合并、拆分、旋转、加水印不是这一份。",
        "questions": [
            ("读完会自己把付款节点写进卡片吗？", "不会。节点是履约那一站的事，而且要你确认。"),
            ("扫描件读不清？", "标明局限，不编一段看起来完整的正文。"),
            ("页数很多会不会只读到一半？", "页数够多、或文件够大时，会走完整认字，避免只吐出前半截。"),
        ],
        "works": [
            "你拿到正文，能看出它是本地抽出的还是认字得到的。",
            "状态表和履约卡片没有因为「只是读一下」被改掉。",
        ],
    },
    {
        "id": "mpp-to-excel",
        "kind": "craft",
        "kind_label": "手艺",
        "mark": "表",
        "title": "进度计划转表",
        "lead": "先认出这是哪种进度，再转成机器能读的表。不写到货日。",
        "mode": "可以单独叫",
        "use": "你说把这份进度转成 Excel 或机读表，转完就停。要到货、验收这些时点，再另说关键节点。",
        "does": "Project 文件、Project 另存的 XML、或一张粗表，转成机读的进度表。需要给人看时，再出一张左边是任务、右边是甘特的 Excel。它不推断关键节点，不写付款区间。你只要这张表，交出来就结束。",
        "when": "你说把 MPP 转成 Excel、把甘特搬进表、认一下这份进度是什么格式。要到货、安装、验收这些完成时点，转完再交给关键节点那一份。系统里走完整条进度链时，也是先经过这里。",
        "questions": [
            ("来的一定是 Project 文件吗？", "不一定。先认格式。已经是任务表的，直接转。"),
            ("那张给人看的甘特 Excel 能再当源转一次吗？", "不能。用旁边的机读表，或回到原来的 Project 文件。"),
            ("转完是不是就有各包的验收日了？", "没有。完成时点是下一份技能的事。"),
        ],
        "works": [
            "同目录有一份机读进度表。你要看的话，还有甘特那张 Excel。",
            "任务行数和起止日期能报出来。没有人猜出来的到货日。",
        ],
    },
    {
        "id": "critical-nodes",
        "kind": "craft",
        "kind_label": "手艺",
        "mark": "点",
        "title": "关键节点",
        "lead": "读懂进度，推出每个包何时完成、何时能请款。对人只说旬。",
        "mode": "可以单独叫",
        "use": "你说看关键节点，或重推某个包的完成时点。只看节点时，不改卡片、不改请款。刚建完一个采购包的那一回合，履约会喊它，只补这个新包。",
        "does": "它读进度表和采购包清单，判断到货、厂验、安装、验收这些完成时点，写进项目的进度数据。请款对齐用完成日。跟你说的时候用「某月上旬 / 中旬 / 下旬」。吃不准就标待确认，不装懂。脚本负责校验和写文件。理解进度这件事要人（或 AI）读过表再定，不能拿关键词对上就算数。",
        "when": "你要关键节点、请款完成时点、倒排到货或验收。刚建好一个采购包，同一回合必须只给这个新包补节点。你只想看节点、不谈建包请款，就停在时间线和进度数据，不去改卡片。",
        "questions": [
            ("对人看的时间线有几份？", "一份。在项目档案的进度计划文件夹里。不要在每个采购包里再放一张。"),
            ("建包脚本不是已经同步时间线了吗？", "那只是重画。节点没有自动补上。补的时候总包那几行要留着。"),
            ("日期吃不准写到哪？", "写在进度数据自己的待确认里，不写进项目那份待确认清单。"),
            ("口头报一个具体日期？", "对人默认报旬。机器里仍存某一天，对齐请款时用完成日。"),
        ],
        "works": [
            "你打开那一份时间线：总包还在，该有的采购包各占一行。",
            "每个节点能说出依据。推断出来的和计划里写明的，分得开。",
            "吃不准的列在待确认里，没有被写成定稿。",
        ],
    },
    {
        "id": "cashflow",
        "kind": "readonly",
        "kind_label": "只读",
        "mark": "钱",
        "title": "现金流预测",
        "lead": "按月看供应商侧还要出去多少。不改任何一本账。",
        "mode": "可以单独叫",
        "use": "你说看现金流、这个月要付多少，它只出预测表。建包或请款办完，它不会自己跟着算，除非你明确要看。",
        "does": "它把各包的付款条件、完成日、已经请过的、变更里已确认的金额拼在一起，按月算出以后要付的钱。变更的增量加在最后一笔。完成日再加 30 天，算钱离开账户的那个月。不算收入。缺日期或缺金额就标出来问你。",
        "when": "你问现金流、资金计划、按月要花多少。建包或请款刚办完，不要自动抢着重算，除非你明确说要看预测。",
        "questions": [
            ("它会把预测写回请款或变更吗？", "不会。只读状态表、卡片、进度和变更台账。"),
            ("变更加在每一笔上吗？", "不加。只加在最后一笔。已取消的变更不算。"),
            ("为什么不是完成当月就出账？", "默认滞后 30 天。你有指定天数或手工改期，按那个来。"),
        ],
        "works": [
            "项目根有一张现金流预测表，能按包、按月看。",
            "缺的日期和金额被标出来，没有被编成一个整数。",
            "采购包状态表、卡片、变更台账和跑之前一样。",
        ],
    },
]


def skill_block(item: dict, source: str) -> str:
    questions = "\n".join(
        f"<div class='q'><p>{html.escape(q)}</p><p>{html.escape(a)}</p></div>"
        for q, a in item["questions"]
    )
    works = "\n".join(f"<li>{html.escape(line)}</li>" for line in item["works"])
    path = f".cursor/skills/{item['id']}/SKILL.md"
    return f"""
<article class="sheet {item['kind']}" id="{item['id']}">
  <a class="tab" href="#{item['id']}">{html.escape(item['mark'])} {html.escape(item['title'])}</a>
  <header class="sheet-head">
    <p class="kind">{html.escape(item['kind_label'])}</p>
    <h2>{html.escape(item['title'])} <code>{html.escape(item['id'])}</code></h2>
    <p class="lead">{html.escape(item['lead'])}</p>
    <p class="mode">{html.escape(item['mode'])}</p>
  </header>
  <section>
    <h3>怎么用</h3>
    <p>{html.escape(item['use'])}</p>
  </section>
  <section>
    <h3>它干什么</h3>
    <p>{html.escape(item['does'])}</p>
  </section>
  <section>
    <h3>什么时候用</h3>
    <p>{html.escape(item['when'])}</p>
  </section>
  <section>
    <h3>你会碰到的问题</h3>
    <div class="qs">{questions}</div>
  </section>
  <section>
    <h3>做成了长这样</h3>
    <ul class="works">{works}</ul>
  </section>
  <details class="source">
    <summary>附上原文 <span>{html.escape(path)}</span></summary>
    <pre>{html.escape(source)}</pre>
  </details>
</article>
"""


def main() -> None:
    blocks = []
    nav = []
    for item in INTROS:
        path = SKILLS / item["id"] / "SKILL.md"
        source = path.read_text(encoding="utf-8")
        if not source.endswith("\n"):
            source += "\n"
        blocks.append(skill_block(item, source))
        nav.append(
            f'<a href="#{item["id"]}" class="{item["kind"]}">{html.escape(item["mark"])} {html.escape(item["title"])}</a>'
        )

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>采购包技能介绍</title>
<style>
  :root {{
    --table: #d5e1e8;
    --sheet: #f4f7f8;
    --ink: #172033;
    --muted: #5c6b78;
    --line: #c3d0d8;
    --station: #1f4e46;
    --entry: #243e5c;
    --craft: #8a4b32;
    --readonly: #3e5870;
    --stamp: #9e2b23;
    --focus: #1f4e46;
  }}
  * {{ box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    margin: 0;
    color: var(--ink);
    background:
      linear-gradient(90deg, rgba(255,255,255,.35) 1px, transparent 1px) 0 0 / 28px 28px,
      var(--table);
    font-family: "Avenir Next", "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", sans-serif;
    font-size: 17px;
    line-height: 1.65;
  }}
  @media (prefers-reduced-motion: reduce) {{
    html {{ scroll-behavior: auto; }}
    * {{ transition: none !important; }}
  }}
  .spine {{
    position: fixed;
    inset: 0 auto 0 0;
    width: 46px;
    background: var(--station);
    color: #e7f2ee;
    z-index: 5;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .spine span {{
    writing-mode: vertical-rl;
    letter-spacing: .55em;
    font-family: "Songti SC", "Noto Serif SC", serif;
    font-size: 15px;
  }}
  main {{
    margin-left: 46px;
    padding: 48px 6vw 96px;
    max-width: 920px;
  }}
  a {{ color: inherit; }}
  :focus-visible {{
    outline: 2px solid var(--focus);
    outline-offset: 3px;
  }}
  .cover {{
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 12px 28px;
    align-items: end;
    margin-bottom: 28px;
  }}
  .kicker {{
    margin: 0;
    letter-spacing: .18em;
    text-transform: uppercase;
    font-size: 12px;
    color: var(--muted);
  }}
  h1 {{
    margin: 6px 0 0;
    font-family: "Songti SC", "Noto Serif SC", serif;
    font-weight: 600;
    font-size: clamp(40px, 6vw, 64px);
    line-height: 1.05;
    letter-spacing: -0.02em;
  }}
  .lede {{
    grid-column: 1 / -1;
    max-width: 40em;
    margin: 8px 0 0;
    font-size: 18px;
  }}
  .chop {{
    width: 92px;
    height: 92px;
    border: 2px solid var(--stamp);
    border-radius: 50%;
    color: var(--stamp);
    display: grid;
    place-items: center;
    transform: rotate(-12deg);
    font-family: "Songti SC", "Noto Serif SC", serif;
    letter-spacing: .2em;
    font-size: 15px;
    background: rgba(255,255,255,.35);
  }}
  .legend {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 8px 0 36px;
  }}
  .legend span, .kind {{
    display: inline-block;
    color: white;
    font-size: 12px;
    letter-spacing: .08em;
    padding: 2px 8px;
    border-radius: 2px;
  }}
  .legend .station, .fork a.station, .index a.station, .sheet.station .tab, .sheet.station .kind {{ background: var(--station); }}
  .legend .entry, .fork a.entry, .index a.entry, .sheet.entry .tab, .sheet.entry .kind {{ background: var(--entry); }}
  .legend .craft, .fork a.craft, .index a.craft, .sheet.craft .tab, .sheet.craft .kind {{ background: var(--craft); }}
  .legend .readonly, .fork a.readonly, .index a.readonly, .sheet.readonly .tab, .sheet.readonly .kind {{ background: var(--readonly); }}
  .map, .sheet {{
    background: var(--sheet);
    border-radius: 0 14px 14px 14px;
    padding: 28px 28px 22px;
    box-shadow: 0 16px 40px rgba(23, 40, 48, .08);
  }}
  .map h2, .sheet h2 {{
    font-family: "Songti SC", "Noto Serif SC", serif;
    font-weight: 600;
    font-size: 28px;
    line-height: 1.25;
    margin: 0 0 8px;
  }}
  .map h2 {{ font-size: 32px; }}
  h3 {{
    margin: 22px 0 8px;
    font-size: 13px;
    letter-spacing: .14em;
    color: #3e4c58;
    font-weight: 600;
  }}
  .rail {{
    margin: 18px 0 0;
    padding: 0;
    list-style: none;
    border-left: 2px solid var(--line);
  }}
  .rail li {{
    margin: 0 0 14px;
    padding: 0 0 0 16px;
  }}
  .rail strong {{ font-weight: 600; }}
  .fork {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-top: 8px;
  }}
  .fork a, .index a {{
    display: block;
    text-decoration: none;
    color: white;
    padding: 8px 10px;
    border-radius: 3px;
    font-size: 14px;
  }}
  .fork a small, .index a small {{ display: block; opacity: .8; font-size: 12px; }}
  .note {{
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid var(--line);
    color: var(--muted);
    font-size: 15px;
  }}
  .index {{
    position: sticky;
    top: 0;
    z-index: 4;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 10px 0 12px;
    margin: 28px 0 8px;
    background: var(--table);
  }}
  .index a {{
    white-space: nowrap;
    color: white;
  }}
  .sheet {{
    position: relative;
    margin-top: 22px;
    scroll-margin-top: 150px;
    border-radius: 12px;
    border-left: 8px solid var(--line);
  }}
  .sheet.station {{ border-left-color: var(--station); }}
  .sheet.entry {{ border-left-color: var(--entry); }}
  .sheet.craft {{ border-left-color: var(--craft); }}
  .sheet.readonly {{ border-left-color: var(--readonly); }}
  .tab {{
    display: inline-flex;
    align-items: center;
    margin: 0 0 12px;
    padding: 3px 10px;
    color: white;
    text-decoration: none;
    border-radius: 3px;
    font-size: 13px;
    letter-spacing: .04em;
  }}
  .sheet-head .kind {{ margin: 0 0 8px; }}
  .sheet-head h2 code, code {{
    font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
    font-size: .72em;
    font-weight: 500;
    color: var(--muted);
  }}
  .lead {{ margin: 0; font-size: 18px; }}
  .mode {{
    display: inline-block;
    margin: 12px 0 0;
    padding: 2px 8px;
    border: 1px solid var(--line);
    border-radius: 2px;
    color: var(--ink);
    background: white;
    font-size: 13px;
    letter-spacing: .04em;
  }}
  .qs {{ display: grid; gap: 10px; }}
  .q {{
    display: grid;
    gap: 4px;
    padding: 12px 0;
    border-top: 1px solid var(--line);
  }}
  .q p {{ margin: 0; }}
  .q p:first-child {{ font-weight: 600; }}
  .works {{ margin: 0; padding-left: 1.1em; }}
  .works li {{ margin: 4px 0; }}
  .source {{ margin-top: 18px; }}
  .source summary {{
    cursor: pointer;
    font-weight: 600;
    list-style: none;
  }}
  .source summary::-webkit-details-marker {{ display: none; }}
  .source summary::before {{
    content: "＋ ";
    color: var(--muted);
  }}
  .source[open] summary::before {{ content: "－ "; }}
  .source summary span {{
    margin-left: 8px;
    font-weight: 400;
    color: var(--muted);
    font-family: "SF Mono", ui-monospace, Menlo, monospace;
    font-size: 12px;
  }}
  pre {{
    margin: 12px 0 0;
    padding: 16px;
    max-height: 70vh;
    overflow: auto;
    background: #172033;
    color: #e7eef2;
    border-radius: 8px;
    font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
    font-size: 12.5px;
    line-height: 1.55;
    white-space: pre-wrap;
  }}
  .toolbar {{
    display: flex;
    justify-content: flex-end;
    margin-top: 18px;
  }}
  button {{
    font: inherit;
    background: transparent;
    color: var(--ink);
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 6px 14px;
    cursor: pointer;
  }}
  button:hover {{ background: white; }}
  footer {{
    margin-top: 36px;
    color: var(--muted);
    font-size: 14px;
  }}
  @media (max-width: 720px) {{
    .spine {{ display: none; }}
    main {{ margin-left: 0; padding: 28px 18px 72px; }}
    .cover {{ grid-template-columns: 1fr; }}
    .chop {{ justify-self: end; }}
    .fork {{ grid-template-columns: 1fr; }}
    .source summary span {{ display: block; margin: 4px 0 0; }}
    .map, .sheet {{ padding: 22px 16px 16px; }}
  }}
</style>
</head>
<body>
<div class="spine" aria-hidden="true"><span>采购包</span></div>
<main>
  <header class="cover">
    <div>
      <p class="kicker">PM Skills · 采购包</p>
      <h1>先看你站在哪一站</h1>
    </div>
    <div class="chop" aria-hidden="true">只指路</div>
    <p class="lede">十一份技能管采购包这一路。履约、请款、变更这三站不用点名：邮件放进待处理，说一声处理，分对了就办。立项要在对话里说。手艺和只读可以单独叫，你只说这件事，就只做这件事。谁先谁后的规矩单写在编排里，它自己不是技能，所以不占这一夹。</p>
  </header>
  <div class="legend" aria-label="四种角色">
    <span class="station">工位 · 邮件分到就办（立项除外）</span>
    <span class="entry">入口 · 你把信放进夹</span>
    <span class="craft">手艺 · 可以单独叫</span>
    <span class="readonly">只读 · 可以单独叫</span>
  </div>

  <section class="map" id="map">
    <h2>主路</h2>
    <p>大多数活沿着这一条走。履约、请款、变更是工位：信分到就办，不用你再点名。手艺和只读可以单独叫。你只说转表、读 PDF、看节点、看现金流，就停在那一份的产出上。</p>
    <ol class="rail">
      <li><strong>立项不走邮件。</strong> <a href="#new-project">项目初始化</a>在对话里说。必填问齐再建立文件夹，这一站不建采购包。给了进度计划或客户请款单，同一回合接着办。待处理邮件里像建项的信不会自动建项目。</li>
      <li><strong>邮件进夹。</strong> 整封信放进「待处理邮件」，说处理。 <a href="#mail-inbox">待处理邮件</a> 负责认这封信是哪一类。</li>
      <li>
        <strong>这封信在办哪一件？</strong>
        <div class="fork">
          <a class="station" href="#po-flow">履约<small>建包、合同、付款条件</small></a>
          <a class="station" href="#payment-flow">请款<small>五步，批复才算已请</small></a>
          <a class="station" href="#change-flow">变更<small>单独一本台账</small></a>
        </div>
      </li>
      <li><strong>手艺在底下被喊，不另开一条业务。</strong> 出卡片会顺手刷请款页。合同先读成文字，再由履约去抽付款节点。进度先转成表，再推关键节点。刚建的包，同一回合只补这个包的节点，总包那几行留着。</li>
      <li><strong>想看以后每个月出去多少。</strong> <a href="#cashflow">现金流预测</a>。你开口要看才算。它不写回请款，也不写回变更。</li>
    </ol>
    <p class="note">单独叫手艺或只读时，不要顺手去建包、改状态表或记已请。三本账仍分开：履约管采购包那一行，请款管请款那四栏，变更管变更台账。</p>
  </section>

  <div class="toolbar">
    <button type="button" id="toggle-src">展开全部原文</button>
  </div>
  <nav class="index" aria-label="技能目录">
    {''.join(nav)}
  </nav>
  {''.join(blocks)}
  <footer>
    <p>每一份先写怎么用：工位是邮件分到就办，手艺和只读可以单独叫。立项不吃待处理邮件。下面再写它干什么、什么时候用、你会碰到的问题、做成了长这样。原文 SKILL.md 附在每份最底下。给 AI 执行时，以展开的原文为准。</p>
  </footer>
</main>
<script>
  const btn = document.getElementById('toggle-src');
  btn.addEventListener('click', () => {{
    const nodes = [...document.querySelectorAll('details.source')];
    const open = nodes.some(d => !d.open);
    nodes.forEach(d => {{ d.open = open; }});
    btn.textContent = open ? '收起全部原文' : '展开全部原文';
  }});
</script>
</body>
</html>
"""
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
