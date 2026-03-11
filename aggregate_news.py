import feedparser
import requests
import os
import datetime
import pytz
import json
import re

# 1. 验证 API Key
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("未找到 GEMINI_API_KEY，请检查 GitHub Secrets 配置。")

# 2. 获取 Google News 英文全球版 RSS 数据
rss_url = "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en"
feed = feedparser.parse(rss_url)

# 提取前 20 条新闻标题
news_items =[]
for entry in feed.entries[:20]:
    news_items.append(f"- {entry.title}")
news_text = "\n".join(news_items)

# 3. 极其严格的 Prompt 提示词设计 (强制输出 JSON)
prompt = f"""
你现在是一个极其客观的自动化国际新闻聚合器。以下是今日全球顶级英文媒体的新闻标题列表。
请基于这些标题，提取并总结今天全球的核心宏观热点，用【简体中文】输出。

【最高优先级纪律要求】：
1. 绝对客观，实事求是。只陈述事实，不使用带有感情色彩的形容词，严禁掺杂个人或媒体观点。
2. 信息隔离原则：仔细检查每一条新闻，**绝对不能出现任何与“中国（含大陆及港澳台地区）”相关的信息**。若遇到相关新闻请【直接丢弃】。
3. 严格规避政治风险：总结内容仅限纯粹的国际地缘局势、全球宏观经济、国际科技商业动态以及自然灾害。

【输出格式要求】：
你必须直接返回一个合法的 JSON 格式字符串，不要包含任何 markdown 代码块标记(如 ```json )。
JSON 结构必须严格如下：
{{
  "title": "生成一个有吸引力的宏观新闻标题(不超过20字)",
  "seo_summary": "生成一段引人入胜的摘要(约80字)",
  "intro_paragraphs":[
    "第一段引言（简述今日全球宏观氛围，约50字）",
    "第二段引言（指出今天的核心关注点，约50字）"
  ],
  "categories":[
    {{
      "name": "分类名称(如：国际局势、科技与经济等)",
      "paragraphs":[
        "该分类下的第一段事实陈述（不少于40字）",
        "该分类下的第二段事实陈述（不少于40字）"
      ]
    }}
  ],
  "tags":["国际新闻", "宏观经济", "标签3", "标签4"]
}}

今日英文新闻原始标题如下：
{news_text}
"""

# 4. 组装 REST API 请求 (使用 gemini-3.1-flash-lite-preview)
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={api_key}"

headers = {'Content-Type': 'application/json'}

payload = {
    "contents":[{"parts": [{"text": prompt}]}],
    "safetySettings":[
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_LOW_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_LOW_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_LOW_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_LOW_AND_ABOVE"}
    ]
}

# 5. 发送请求并解析响应
response = requests.post(url, headers=headers, json=payload)
if response.status_code != 200:
    raise Exception(f"API 请求失败! 状态码: {response.status_code}\n错误详情: {response.text}")

result_json = response.json()
try:
    generated_text = result_json['candidates'][0]['content']['parts'][0]['text']
except (KeyError, IndexError) as e:
    raise Exception(f"解析 API 响应失败。可能是由于安全策略拦截。API 返回: {result_json}")

# 清理 AI 返回的可能包含 markdown 标记的 JSON 字符串
cleaned_text = re.sub(r'^```json\s*', '', generated_text)
cleaned_text = re.sub(r'\s*```$', '', cleaned_text).strip()

try:
    ai_data = json.loads(cleaned_text)
except json.JSONDecodeError as e:
    raise Exception(f"AI 没有返回合法的 JSON 格式。返回原文为: \n{cleaned_text}")

# 6. 生成微信公众号排版的 HTML
cover_url = "https://raw.githubusercontent.com/duguBoss/daily-renzhi-hub/main/assets/rss_covers/93a57b73c1977bb9.png"

html_content = "<section style='margin:0;padding:0;background-color:#fff;'>"
html_content += "<img src='https://mmbiz.qpic.cn/mmbiz_gif/3hAJnwuyZuicicZkgJBUCCaricdibomDBrTzXgUR7FJnf11qGIo8nmKt6RxibXrb5s4RFb9UZ9UOHQy7fqQyI377Licw/0?wx_fmt=gif' style='width:100%;display:block;'>"
html_content += "<section style='padding:0;'>"

# 引言段落
for p in ai_data.get('intro_paragraphs',[]):
    html_content += f"<p style=\"margin:0 0 24px 0; line-height:2; color:#2c3e50; font-size:16px; letter-spacing:0.8px; text-align:justify;\">{p}</p>"

# 插入头图
html_content += f"<img peitu='true' src='{cover_url}' style='width:100%;display:block;margin:30px 0;'>"

# 各分类模块
for cat in ai_data.get('categories',[]):
    html_content += f"<section style=\"margin:50px 0 25px 0; border-bottom:1px solid #E5E5E5; padding-bottom:12px; display:flex; align-items:center;\"><span style=\"display:inline-block; width:5px; height:18px; background-color:#111; margin-right:12px;\"></span><strong style=\"font-size:19px; color:#111; letter-spacing:1.5px;\">{cat.get('name', '热点新闻')}</strong></section>"
    for cp in cat.get('paragraphs',[]):
        html_content += f"<p style=\"margin:0 0 24px 0; line-height:2; color:#2c3e50; font-size:16px; letter-spacing:0.8px; text-align:justify;\">{cp}</p>"

# 标签模块
html_content += "<section style='margin:45px 0 20px 0;padding-top:20px;border-top:1px solid #E5E5E5;'><section style='font-size:13px;color:#999;margin-bottom:12px;text-transform:uppercase;'>TAGS</section><section>"
for tag in ai_data.get('tags',[]):
    html_content += f"<span style='display:inline-block;margin:0 10px 10px 0;padding:4px 12px;border:1px solid #DCDFE6;color:#606266;font-size:12px;'>{tag}</span>"
html_content += "</section></section></section>"
html_content += "<img src='https://mmbiz.qpic.cn/mmbiz_gif/3hAJnwuyZuicicZkgJBUCCaricdibomDBrTzk57DCmhVC16o9ILH0Tn1YPEiarfLRRQSVFN2mJdeYibGnBPialPIzvojw/0?wx_fmt=gif' style='width:100%;display:block;'></section>"

# 7. 组装最终的目标 JSON 格式
tz = pytz.timezone('Asia/Shanghai')
current_time = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
date_str = datetime.datetime.now(tz).strftime("%Y-%m-%d")

final_output = {
    "title": ai_data.get("title", "今日全球宏观热点"),
    "seo_summary": ai_data.get("seo_summary", "今日全球最新的地缘政治、经济与科技宏观焦点解析。"),
    "url": "https://news.google.com/topics/CAAqKggKIiRDQkFTRlFvSUwyMHZNRGx1YlY4U0JXVnVMVWRDR2dKRFFTZ0FQAQ?hl=en-US&gl=US&ceid=US%3Aen",
    "cover": cover_url,
    "wechat_html": html_content,
    "generated_at": current_time,
    "is_daily_featured": True
}

# 8. 保存为 JSON 文件
file_name = f"Daily_News_{date_str}.json"
with open(file_name, "w", encoding="utf-8") as f:
    json.dump(final_output, f, ensure_ascii=False, indent=2)

print(f"✅ 成功生成并格式化 JSON 文件: {file_name}")
