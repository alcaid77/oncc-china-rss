
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from xml.etree.ElementTree import Element, SubElement, ElementTree
from datetime import datetime, timezone
from email.utils import format_datetime
import re
import time

SOURCE_URL = "https://hk.on.cc/hk/news/index.html"
OUTPUT_FILE = "feed.xml"
MAX_ITEMS = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}

session = requests.Session()
session.headers.update(HEADERS)


def get_soup(url):
    r = session.get(url, timeout=25)
    r.raise_for_status()
    # 使用原始字节交由 BeautifulSoup 自动识别网页编码
    return BeautifulSoup(r.content, "html.parser")


def clean_text(text):
    if not text:
        return ""
    text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_article_description(url):
    """从单篇新闻网页的 meta description / OG description 取得简介"""
    try:
        soup = get_soup(url)

        for attr, key in [
            ("name", "description"),
            ("property", "og:description"),
            ("name", "twitter:description"),
        ]:
            tag = soup.find("meta", attrs={attr: key})
            if tag and tag.get("content"):
                desc = clean_text(tag["content"])
                if desc:
                    return desc[:800]

        # 如果没有 meta 简介，尝试提取正文段落
        article = soup.find("article")
        if article:
            paragraphs = [
                clean_text(p.get_text(" ", strip=True))
                for p in article.find_all("p")
            ]
            paragraphs = [p for p in paragraphs if len(p) > 30]
            if paragraphs:
                return " ".join(paragraphs[:3])[:800]

    except Exception as e:
        print(f"获取简介失败: {url} ({e})")

    return ""


def get_article_date(soup, url):
    """尝试获取文章发布日期"""
    date_candidates = [
        soup.find("meta", attrs={"property": "article:published_time"}),
        soup.find("meta", attrs={"name": "pubdate"}),
        soup.find("meta", attrs={"name": "publishdate"}),
        soup.find("meta", attrs={"name": "date"}),
    ]

    for tag in date_candidates:
        if tag and tag.get("content"):
            try:
                value = tag["content"].replace("Z", "+00:00")
                dt = datetime.fromisoformat(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return format_datetime(dt.astimezone(timezone.utc))
            except Exception:
                pass

    # 从东网新闻网址中的日期目录推断日期
    match = re.search(r"/cnt/news/(\d{8})/", url)
    if match:
        try:
            dt = datetime.strptime(match.group(1), "%Y%m%d")
            dt = dt.replace(tzinfo=timezone.utc)
            return format_datetime(dt)
        except Exception:
            pass

    return None


# 抓取中港台栏目首页
soup = get_soup(SOURCE_URL)
news_list = []
seen_urls = set()

for a in soup.find_all("a", href=True):
    title = clean_text(a.get_text(" ", strip=True))
    url = urljoin(SOURCE_URL, a["href"])
    path = urlparse(url).path

    # 只保留东网新闻文章链接
    if "on.cc" not in urlparse(url).netloc:
        continue
    if not re.search(r"/bkn/cnt/news/\d{8}/[^/]+\.html$", path):
        continue
    if len(title) < 6 or url in seen_urls:
        continue

    seen_urls.add(url)
    news_list.append({"title": title, "url": url})

# RSS 2.0
rss = Element("rss", version="2.0")
channel = SubElement(rss, "channel")

SubElement(channel, "title").text = "东网中港台新闻 RSS"
SubElement(channel, "link").text = SOURCE_URL
SubElement(channel, "description").text = "东网中港台栏目新闻"
SubElement(channel, "language").text = "zh-HK"
SubElement(channel, "lastBuildDate").text = format_datetime(
    datetime.now(timezone.utc)
)

count = 0

for news in news_list[:MAX_ITEMS]:
    print("抓取:", news["title"])

    item_soup = None
    description = get_article_description(news["url"])

    # 尝试再次获取文章日期
    try:
        item_soup = get_soup(news["url"])
    except Exception as e:
        print("获取文章日期失败:", e)

    item = SubElement(channel, "item")
    SubElement(item, "title").text = news["title"]
    SubElement(item, "link").text = news["url"]
    SubElement(item, "guid", isPermaLink="true").text = news["url"]

    # 没有可靠简介时，使用标题，不拼接其他新闻内容
    SubElement(item, "description").text = description or news["title"]

    if item_soup:
        pubdate = get_article_date(item_soup, news["url"])
        if pubdate:
            SubElement(item, "pubDate").text = pubdate

    count += 1
    time.sleep(0.3)

ElementTree(rss).write(
    OUTPUT_FILE,
    encoding="utf-8",
    xml_declaration=True
)

print(f"RSS生成成功，共 {count} 条新闻")
