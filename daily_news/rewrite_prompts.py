"""Rewrite prompt templates for fixing content length issues."""
from __future__ import annotations

from typing import Any


def build_card_rewrite_prompt(
    card_number: int,
    article: dict[str, Any],
    date_str: str,
    previous_attempt: dict[str, Any],
    paragraph_lengths: list[int],
) -> str:
    """Build rewrite prompt based on previous attempt to fix length issues."""
    # Build feedback about what went wrong
    feedback_parts = []
    for i, length in enumerate(paragraph_lengths):
        if length < 200:
            feedback_parts.append(
                f"❌ 第{i+1}段：当前只有{length}字，严重不足！需要增加{200-length}字以上"
            )
        elif length > 300:
            feedback_parts.append(
                f"❌ 第{i+1}段：当前有{length}字，太长了！需要减少{length-300}字"
            )

    feedback = "\n".join(feedback_parts) if feedback_parts else "字数需要调整"

    # Include last generated content
    last_paragraphs = previous_attempt.get("paragraphs", [])
    last_content_text = ""
    if last_paragraphs:
        last_content_text = "\n\n【上次生成的完整内容 - 请在此基础上修改，不要从头重写】\n"
        for i, para in enumerate(last_paragraphs):
            length = paragraph_lengths[i] if i < len(paragraph_lengths) else len(para)
            last_content_text += f"\n第{i+1}段（当前{length}字）：\n{para}\n"

    # Build adjustment guide
    adjustment_parts = []
    for i, length in enumerate(paragraph_lengths):
        if length < 200:
            adjustment_parts.append(
                f"""【第{i+1}段如何增加字数（当前{length}字，需增加{200-length}字以上）】
- 在现有内容基础上扩展，不要删除已有内容
- 添加更多细节：具体时间、数据、背景信息
- 详细解释相关概念和影响
- 补充例子或对比说明"""
            )
        elif length > 300:
            adjustment_parts.append(
                f"""【第{i+1}段如何减少字数（当前{length}字，需减少{length-300}字）】
- 精简表达，删除冗余词语
- 合并相似句子
- 保留核心信息，删除次要细节"""
            )

    adjustment_guide = (
        "\n\n".join(adjustment_parts)
        if adjustment_parts
        else "【字数调整指南】\n- 检查每段字数，确保在200-300字范围内"
    )

    article_block = f"""【文章素材】
标题：{article.get('title_cn', article.get('title', ''))}
英文标题：{article.get('title', '')}
来源：{article.get('source', '国际媒体')}
摘要：{article.get('summary_cn', article.get('summary', ''))}
内容：{article.get('content', article.get('summary', ''))[:1000]}..."""

    return f"""你是国际新闻中文编辑，需要重新撰写新闻内容以符合字数要求。

【任务】
为第{card_number}篇新闻重新撰写中文内容。

日期：{date_str}

{article_block}

【问题反馈】
{feedback}
{last_content_text}

{adjustment_guide}

【硬性要求 - 必须满足】
- 第1段：200-300个汉字
- 第2段：200-300个汉字
- 写完后逐字统计，确认符合要求后再输出

【输出格式】
只输出JSON，不要任何其他文字：
{{"title": "中文标题", "paragraphs": ["第1段内容（200-300字）...", "第2段内容（200-300字）..."]}}
"""
