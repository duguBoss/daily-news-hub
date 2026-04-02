"""HTML and Markdown templates for rendering."""
from __future__ import annotations

# HTML Template Components
HTML_WRAPPER_START = """<section style="margin:0;padding:0;background:#ffffff;">
<img src="{top_banner}" style="width:100%;display:block;">
<section style="max-width:760px;margin:0 auto;padding:2px;">
"""

HTML_HEADER = """<section style="margin:12px 0 16px 0;padding:2px 2px 8px 2px;border-bottom:2px solid #1e293b;">
<div style="font-size:12px;letter-spacing:2px;color:#b59f7b;text-transform:uppercase;margin-bottom:4px;font-weight:600;">Global Briefing</div>
<h1 style="margin:0;font-size:26px;line-height:1.4;color:#0f172a;font-weight:bold;letter-spacing:0.5px;">{title}</h1>
</section>
"""

HTML_ARTICLE_START = """<section style="margin:0 0 18px 0;padding:0 2px 14px 2px;border-bottom:1px solid #f1f5f9;">
<h2 style="margin:0 0 12px 0;padding-left:10px;border-left:4px solid #b59f7b;font-size:20px;line-height:1.5;color:#1e293b;letter-spacing:0.5px;">{title}</h2>
"""

HTML_ARTICLE_IMAGE = """<section style="margin:0 0 10px 0;">
<img src="{url}" style="width:100%;display:block;border-radius:4px;border:1px solid #f1f5f9;">
</section>
"""

HTML_PARAGRAPH = '<p style="margin:0 0 6px 0;line-height:1.8;color:#334155;font-size:16px;letter-spacing:0.5px;text-align:justify;">{text}</p>'

HTML_ARTICLE_END = """<div style="margin-top:8px;text-align:right;">
<span style="display:inline-block;font-size:11px;letter-spacing:1px;color:#94a3b8;text-transform:uppercase;border-bottom:1px solid #f1f5f9;padding-bottom:2px;">Global Watch</span>
</div>
</section>
"""

HTML_EDITORIAL = """<section style="margin:16px 2px;padding:14px;background:#0f172a;border-top:3px solid #b59f7b;border-radius:2px;">
<div style="font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#b59f7b;margin-bottom:8px;font-weight:600;">Risk Watch</div>
<p style="margin:0 0 6px 0;font-size:15px;line-height:1.8;color:#e2e8f0;text-align:justify;"><strong>趋势：</strong>{timeline}</p>
<p style="margin:0;font-size:15px;line-height:1.8;color:#e2e8f0;text-align:justify;"><strong>关注：</strong>{risk_watch}</p>
</section>
"""

HTML_TAGS_START = """<section style="margin:12px 2px 0 2px;padding-top:12px;border-top:1px dashed #cbd5e1;">
<div style="font-size:12px;letter-spacing:1px;color:#64748b;text-transform:uppercase;margin-bottom:8px;">Keywords</div>
"""

HTML_TAG = '<span style="display:inline-block;margin:0 8px 8px 0;padding:4px 10px;border:1px solid #e2e8f0;border-radius:2px;background:#f8fafc;color:#475569;font-size:12px;letter-spacing:0.5px;">{tag}</span>'

HTML_WRAPPER_END = """</section></section>
<img src="{bottom_banner}" style="width:100%;display:block;">
</section>
"""

# Markdown Templates
MD_HEADER = "# {title}\n"
MD_ARTICLE_HEADER = "\n## {title}\n"
MD_ARTICLE_IMAGE = "配图：{url}\n"
MD_EDITORIAL_HEADER = "\n## 编辑注\n"
MD_TIMELINE = "- 新闻节奏：{timeline}\n"
MD_RISK_WATCH = "- 风险观察：{risk_watch}\n"
MD_SOURCES_HEADER = "\n## 原始素材\n"
MD_SOURCE_ITEM = "- [{index}] {title} | {url}\n"
MD_TAGS = "\n标签：{tags}\n"
