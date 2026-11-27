
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from xml.etree.ElementTree import Element, SubElement, ElementTree
from datetime import datetime, timezone
import html
import re

SOURCE_URL = "https://hk.on.cc/hk/news/index.html"
FEED_URL = "https://raw.githubusercontent.com/YOUR_USERNAME/oncc-china-rss/main/feed.xml"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
}

response = requests.get(SOURCE_URL, headers=headers, timeout=30)
response.raise_for_status()
soup = BeautifulSoup(response.text, "html.parser")

items = []
seen = set()

# 只提取当前中港台栏目页面中的新闻链接
for a in soup.find_all("a", href=True):
    title = a.get_text(" ", strip=True)
    url = urljoin(SOURCE_URL, a["href"])

    if not title or len(title) < 6:
        continue

    parsed = urlparse(url)

    # 限定东网域名及新闻文章链接
    if parsed.netloc not in ("hk.on.cc", "on.cc"):
        continue
    if "/bkn/cnt/" not in parsed.path:
        continue
    if url in seen:
        continue

    seen.add(url)

    # 从新闻链接周围提取简要介绍
    description = ""
    node = a

    for _ in range(5):
        if node.parent:
            node = node.parent
        text = node.get_text(" ", strip=True)
        if len(text) > len(title) + 20 and len(text) < 1200:
            description = text.replace(title, "", 1).strip()
            break

    description = re.sub(r"\s+", " ", description)
    description = description[:500]

    items.append({
        "title": title,
        "url": url,
        "description": description
    })

# 建立 RSS 2.0
rss = Element("rss", version="2.0")
channel = SubElement(rss, "channel")

SubElement(channel, "title").text = "东网中港台新闻 RSS"
SubElement(channel, "link").text = SOURCE_URL
SubElement(channel, "description").text = "东网中港台栏目新闻，包含标题、链接及新闻简介"
SubElement(channel, "language").text = "zh-HK"
SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime(
    "%a, %d %b %Y %H:%M:%S GMT"
)

for news in items[:60]:
    item = SubElement(channel, "item")
    SubElement(item, "title").text = news["title"]
    SubElement(item, "link").text = news["url"]
    SubElement(item, "guid", isPermaLink="true").text = news["url"]
    SubElement(item, "description").text = news["description"] or news["title"]

    SubElement(item, "pubDate").text = datetime.now(timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )

ElementTree(rss).write("feed.xml", encoding="utf-8", xml_declaration=True)

print(f"RSS生成成功，共抓取 {len(items)} 条新闻")
