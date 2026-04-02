"""Prompt templates for AI content generation."""
from __future__ import annotations

import json
from typing import Any


# Forbidden terms for titles
FORBIDDEN_TITLE_TERMS = (
    "3条", "三条", "要闻", "速报", "汇总", "盘点", "合集",
    "冲刺", "开扯", "扒一扒", "扒", "盘", "重磅", "来了",
    "刚刚", "揭秘", "真相", "震惊", "倒计时", "里程碑",
)

TITLE_STYLE_HINT = "标题要像成熟中文科技自媒体，不要像栏目名或低信息量摘要"


def build_title_prompt(
    date_str: str, articles: list[dict[str, Any]], recent_titles: list[str]
) -> str:
    """Build prompt for generating main title - Step 1."""
    facts = []
    for art in articles[:5]:
        title = art.get("title_cn", art.get("title", ""))
        if title:
            facts.append(title)

    return f"""你是国际新闻中文媒体主编，为今日全球新闻撰写简报标题。

【今日素材要点】
{chr(10).join(f"- {f}" for f in facts) if facts else "全球重要新闻动态"}

【近期已用标题】（严禁重复或雷同）
{json.dumps(recent_titles[:12], ensure_ascii=False)}

【标题撰写规范 - 严格遵守】
1. 字数要求（最重要）：
   - 必须严格控制在20-30个汉字之间（不含标点）
   - 少于20字或超过30字都是不合格的
   - 写完后必须自己数一遍字数，确保符合要求
   - 最佳长度：24-28字

2. 结构公式：[核心主体] + [关键动作/状态] + [具体细节/意义]
   - 核心主体：具体国家/地区、组织、事件名
   - 关键动作：宣布、达成、发布、调整、冲突、合作
   - 具体细节：时间节点、数据、影响范围

3. 风格要求：
   - 信息密度高，每字都有信息量
   - 专业但不晦涩，像资深国际观察者的口吻
   - 禁止：{', '.join(FORBIDDEN_TITLE_TERMS)}
   - 禁止：数字概括（如"3大看点"）、情绪煽动词、空洞形容词堆砌

4. 差异化原则：
   - 必须基于今日素材的独特事实
   - 每个标题应该是"只有今天才能这么写"

【字数检查步骤 - 必须执行】
1. 先写出标题草稿
2. 数一下汉字数量（不含标点符号）
3. 如果少于20字，增加具体细节
4. 如果超过30字，精简修饰词
5. 确认20-30字范围内后，再输出

【输出要求】
- 只输出标题文字，无引号、无说明、无JSON
- 必须是纯中文
- 标题必须自然流畅

输出："""


def build_article_card_prompt(
    card_number: int, article: dict[str, Any], date_str: str
) -> str:
    """Build prompt for generating a single article card content - Step 2/3/4."""
    article_block = f"""【文章素材】
标题：{article.get('title_cn', article.get('title', ''))}
英文标题：{article.get('title', '')}
来源：{article.get('source', '国际媒体')}
时间：{article.get('publish_time', '')}
摘要：{article.get('summary_cn', article.get('summary', ''))}
内容：{article.get('content', article.get('summary', ''))[:1000]}..."""

    return f"""你是国际新闻中文编辑，为中文读者撰写新闻解读内容。

【任务】
为第{card_number}篇新闻撰写中文内容。

日期：{date_str}

{article_block}

【字数要求 - 必须严格遵守】
⚠️ 写2个段落，每段必须包含200-300个汉字（这是硬性要求）
⚠️ 每段少于200字或多于300字都是不合格的
⚠️ 写完后必须逐字统计，确保符合要求
⚠️ 最佳长度：每段250字左右，两段共500字左右

【内容结构要求】
第1段（200-300字）：事件介绍
- 简要介绍这是什么事件/动态
- 详细说明关键信息：时间、地点、参与方、关键数据
- 背景信息和事件经过

第2段（200-300字）：影响与分析
- 这个事件的重要性
- 可能带来的影响和后果
- 对相关方或全球的意义

注意：内容本身要有价值和深度，不要写"这对读者很有意义"这类直白的话，让价值通过内容自然体现

【写作要求】
- 使用自然、直接的语言，像给朋友分享重要新闻
- 保留重要的英文术语（首次出现时带中文解释）
- 所有文字必须是简体中文
- 避免模板化表达，像专业新闻评论员一样写作
- 确保内容对读者有实际价值，不要空洞的描述

【标题要求】
- 15-25字，信息丰富
- 包含具体国家/组织/事件名
- 不要"全球新闻"这类泛泛标题
- 不要用"盘"、"扒"、"开扯"等网络用语

【输出格式】
只输出JSON，不要任何其他文字：
{{"title": "中文标题", "paragraphs": ["第1段内容（200-300字）...", "第2段内容（200-300字）..."]}}

【参考示例】
标题：美联储维持利率不变，暗示年内或有一次降息
第1段（约250字）：美国联邦储备委员会在最新货币政策会议上宣布维持基准利率在5.25%-5.50%区间不变，这一决定符合市场预期。美联储主席在新闻发布会上表示，尽管通胀数据近期有所回落，但仍高于2%的目标水平，因此需要更多证据确认通胀持续降温的趋势。会议声明中提到，劳动力市场依然强劲，失业率维持在历史低位，但经济增长动能有所放缓。这一政策立场反映了美联储在控制通胀与支持经济增长之间的谨慎平衡。

第2段（约250字）：市场分析师普遍认为，此次利率决议释放了鸽派信号，暗示美联储可能在年内启动降息周期。根据利率期货数据，投资者目前预计9月首次降息的概率超过70%。这一预期对全球金融市场产生重要影响，美元指数在决议公布后小幅下跌，而新兴市场货币普遍走强。对于全球经济而言，美联储政策转向将缓解发展中国家的资本外流压力，但同时也需要关注美国经济增长放缓可能带来的外溢效应。
"""


def build_editorial_notes_prompt(
    articles: list[dict[str, Any]], date_str: str
) -> str:
    """Build prompt for generating editorial notes."""
    articles_text = "\n\n".join(
        f"[{i+1}] {a.get('title_cn', a.get('title', ''))}\n{a.get('summary_cn', a.get('summary', ''))[:200]}"
        for i, a in enumerate(articles[:6])
    )

    return f"""基于以下新闻素材，生成编辑点评内容。

日期：{date_str}

新闻素材：
{articles_text}

请生成以下内容（JSON格式）：
{{
  "timeline": "新闻趋势分析（80-120字，分析今日新闻的整体趋势和特点）",
  "risk_watch": "风险观察（80-120字，指出需要关注的风险点或不确定性）",
  "tags": ["标签1", "标签2", "标签3", "标签4", "标签5"]
}}

要求：
1. 使用简体中文
2. 内容专业、客观
3. 标签要具体，避免"国际新闻"这种泛泛标签
4. 只输出JSON，不要其他内容
"""
