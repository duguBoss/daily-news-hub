import feedparser
import requests
import os
import datetime
import pytz

# 1. 验证 API Key
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("未找到 GEMINI_API_KEY，请检查 GitHub Secrets 配置。")

# 2. 获取 Google News 英文全球版 RSS 数据
rss_url = "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en"
feed = feedparser.parse(rss_url)

# 提取前 20 条新闻标题
news_items = []
for entry in feed.entries[:20]:
    news_items.append(f"- {entry.title}")
news_text = "\n".join(news_items)

# 3. 极其严格的 Prompt 提示词设计
prompt = f"""
你现在是一个极其客观的自动化国际新闻聚合器。以下是今日全球顶级英文媒体的新闻标题列表。
请基于这些标题，提取并总结今天全球的核心宏观热点，用【简体中文】输出。

必须严格遵守以下最高优先级的纪律要求（如果违反将导致系统崩溃）：
1. 绝对客观，实事求是。只陈述事实，不使用任何带有感情色彩、煽动性或评价性的形容词，严禁掺杂任何个人或媒体观点。
2. 信息隔离原则：仔细检查每一条新闻，**绝对不能出现任何与“中国（含大陆及港澳台地区）”相关的信息**。若原新闻列表中包含涉及中国的外交、经济、政治、企业等相关新闻，请【直接丢弃、忽略】，不要对其进行任何翻译和总结。
3. 严格规避政治风险：总结内容仅限纯粹的国际地缘局势、全球宏观经济（如美联储降息）、国际科技商业动态（如AI发展）以及自然灾害。
4. 结构化输出：将剩下的纯国际新闻分为 2-3 个分类（如：国际局势、全球经济、科技动态），每个分类下用无序列表简述事实即可。不需要过度展开。

今日英文新闻原始标题如下：
{news_text}
"""

# 4. 组装 REST API 请求 (使用指定的 gemini-3.1-flash-lite-preview)
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={api_key}"

headers = {
    'Content-Type': 'application/json'
}

payload = {
    "contents":[{
        "parts": [{"text": prompt}]
    }],
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
    raise Exception(f"解析 API 响应失败。这可能是由于安全策略拦截了内容。API 原始返回内容: {result_json}")

# 6. 生成并保存 Markdown 文件
# 获取当前北京时间
tz = pytz.timezone('Asia/Shanghai')
today_str = datetime.datetime.now(tz).strftime("%Y-%m-%d")

markdown_content = f"# 全球宏观热点简报 ({today_str})\n\n"
markdown_content += "> 本简报由自动脚本聚合英文主流媒体新闻并调用 `gemini-3.1-flash-lite-preview` 生成。内容坚持客观中立原则，仅关注纯国际宏观议题。\n\n"
markdown_content += generated_text

# 保存到本地文件
file_name = f"Daily_News_{today_str}.md"
with open(file_name, "w", encoding="utf-8") as f:
    f.write(markdown_content)

print(f"✅ {file_name} 生成成功！")
