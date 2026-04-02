"""Prompt templates for AI content generation."""
from __future__ import annotations


def build_translation_prompt(title: str, summary: str) -> str:
    """Build prompt for translating news items."""
    return f"""请将以下英文新闻标题和摘要翻译成中文。

标题：{title}
摘要：{summary}

要求：
1. 标题简洁有力，不超过20字
2. 摘要准确传达核心信息，语言流畅自然
3. 专业术语保持准确性
4. 首次出现的英文专业术语请在括号内注明英文原文

请以JSON格式返回：
{{
  "title_cn": "中文标题",
  "summary_cn": "中文摘要"
}}"""


def build_editorial_prompt(articles_text: str) -> str:
    """Build prompt for generating editorial content."""
    return f"""基于以下新闻素材，生成编辑内容。

新闻素材：
{articles_text}

请生成以下内容（JSON格式）：
{{
  "title": "简报标题（简洁有力，10-15字）",
  "seo_summary": "SEO摘要（50-80字，包含关键词）",
  "intro_paragraphs": ["导语段落1", "导语段落2"],
  "editorial_notes": {{
    "timeline": "新闻趋势分析（100字左右）",
    "risk_watch": "风险观察（100字左右）"
  }},
  "tags": ["标签1", "标签2", "标签3", "标签4", "标签5"]
}}"""


def build_article_selection_prompt(articles_text: str, count: int = 6) -> str:
    """Build prompt for selecting featured articles."""
    return f"""从以下新闻中精选{count}篇最重要的文章。

{articles_text}

选择标准：
1. 全球影响力和重要性
2. 时效性和新闻价值
3. 内容多样性（政治、经济、科技、社会等）
4. 避免重复主题

请以JSON格式返回选中文章的索引（从1开始）：
{{
  "selected_indices": [1, 3, 5, 7, 9, 12]
}}"""


def build_summary_prompt(title: str, content: str) -> str:
    """Build prompt for generating article summary."""
    return f"""请为以下新闻生成中文摘要。

标题：{title}
内容：{content[:2000]}

要求：
1. 字数：400-500个汉字
2. 内容：第一段介绍事件背景和关键信息，第二段分析影响和意义
3. 语言：专业、客观、流畅
4. 首次出现的英文术语请在括号内注明原文

直接返回摘要文本，不要添加标题或其他说明。"""
