
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from xml.etree.ElementTree import Element, SubElement, ElementTree
from datetime import datetime, timezone
import re

SOURCE_URL = "https://hk.on.cc/hk/news/index.html"
OUTPUT_FILE = "feed.xml"
MAX_ITEMS = 40

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}


def fix_text(text):
    """修复 UTF-8 被误解码成 Latin-1 的中文乱码"""
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text).strip()

    # 仅当出现明显乱码特征时尝试反向编码
    markers = (
        "Ã", "Â", "æ", "ç", "è", "é", "å", "ä",
        "ï", "ð", "ã", "¤", "§", "¦", "¬", "»"
    )

    if any(marker in text for marker in markers):
        try:
            repaired = text.encode("latin1").decode("utf-8")
            if repaired:
                text = repaired
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

    return text


def get_page():
    response = requests.get(SOURCE_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    # 不使用 response.text，避免 requests 错误猜测编码
    return BeautifulSoup(response.content, "html.parser")


soup = get_page()
news_list = []
seen = set()

for a in soup.find_all("a", href=True):
    raw_title = a.get_text(" ", strip=True)
    title = fix_text(raw_title)

    url = urljoin(SOURCE_URL, a["href"])
    parsed = urlparse(url)
    path = parsed.path

    # 仅东网中港台栏目中符合新闻文章格式的链接
    if parsed.netloc not in ("hk.on.cc", "on.cc"):
        continue

    if not re.search(
        r"/bkn/cnt/news/\d{8}/[^/]+\.html$",
        path
    ):
        continue

    if len(title) < 6 or url in seen:
        continue

    seen.add(url)

    news_list.append({
        "title": title,
        "url": url
    })

# 创建 RSS 2.0
rss = Element("rss", version="2.0")
channel = SubElement(rss, "channel")

SubElement(channel, "title").text = "东网中港台新闻 RSS"
SubElement(channel, "link").text = SOURCE_URL
SubElement(channel, "description").text = (
    "东网中港台新闻，自动修复中文编码"
)
SubElement(channel, "language").text = "zh-HK"
SubElement(channel, "lastBuildDate").text = datetime.now(
    timezone.utc
).strftime("%a, %d %b %Y %H:%M:%S GMT")

count = 0

for news in news_list[:MAX_ITEMS]:
    item = SubElement(channel, "item")

    SubElement(item, "title").text = news["title"]
    SubElement(item, "link").text = news["url"]
    SubElement(item, "guid", isPermaLink="true").text = news["url"]

    # 暂时使用自己的标题作为简介，避免串入其他新闻
    SubElement(item, "description").text = news["title"]

    count += 1

ElementTree(rss).write(
    OUTPUT_FILE,
    encoding="utf-8",
    xml_declaration=True
)

print(f"RSS生成成功，共 {count} 条新闻")
