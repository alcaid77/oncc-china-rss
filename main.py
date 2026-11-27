
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from xml.etree.ElementTree import Element, SubElement, ElementTree
from datetime import datetime, timezone
import re
import time

SOURCE_URL = "https://hk.on.cc/hk/news/index.html"
OUTPUT_FILE = "feed-v2.xml"
MAX_ITEMS = 40
MAX_SUMMARY_LENGTH = 600

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}

session = requests.Session()
session.headers.update(HEADERS)


def fix_text(text):
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text).strip()

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


def get_soup(url):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.content, "html.parser")


def clean_text(text):
    text = BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)
    text = fix_text(text)
    return re.sub(r"\s+", " ", text).strip()


def get_summary(url, title):
    """从单篇新闻网页提取独立摘要，避免串入其他新闻"""

    try:
        soup = get_soup(url)

        # 优先使用新闻页面的摘要 Meta 标签
        meta_candidates = [
            {"property": "og:description"},
            {"name": "description"},
            {"name": "twitter:description"},
        ]

        for attrs in meta_candidates:
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content"):
                summary = clean_text(tag["content"])
                if summary and summary != title and len(summary) > 20:
                    return summary[:MAX_SUMMARY_LENGTH]

        # Meta 摘要没有内容时，尝试提取单篇文章正文
        containers = [
            soup.find("article"),
            soup.find("main"),
            soup.find(attrs={"itemprop": "articleBody"}),
        ]

        for container in containers:
            if not container:
                continue

            # 删除非正文元素
            for unwanted in container.find_all(
                ["script", "style", "nav", "header", "footer", "aside"]
            ):
                unwanted.decompose()

            paragraphs = []
            for p in container.find_all("p"):
                text = clean_text(p.get_text(" ", strip=True))

                # 排除太短、重复标题、导航或无意义内容
                if len(text) < 25:
                    continue
                if text == title or title in text:
                    continue

                paragraphs.append(text)

            if paragraphs:
                summary = " ".join(paragraphs[:5])
                summary = re.sub(r"\s+", " ", summary).strip()
                return summary[:MAX_SUMMARY_LENGTH]

    except Exception as e:
        print(f"摘要抓取失败: {url} ({e})")

    # 无法取得正文时才使用标题
    return title


# 抓取中港台栏目
soup = get_soup(SOURCE_URL)
news_list = []
seen = set()

for a in soup.find_all("a", href=True):
    title = fix_text(a.get_text(" ", strip=True))
    url = urljoin(SOURCE_URL, a["href"])
    parsed = urlparse(url)

    if parsed.netloc not in ("hk.on.cc", "on.cc"):
        continue

    if not re.search(
        r"/bkn/cnt/news/\d{8}/[^/]+\.html$",
        parsed.path
    ):
        continue

    if len(title) < 6 or url in seen:
        continue

    seen.add(url)
    news_list.append({"title": title, "url": url})


# 生成 RSS 2.0
rss = Element("rss", version="2.0")
channel = SubElement(rss, "channel")

SubElement(channel, "title").text = "东网中港台新闻 RSS"
SubElement(channel, "link").text = SOURCE_URL
SubElement(channel, "description").text = "东网中港台新闻，含新闻摘要"
SubElement(channel, "language").text = "zh-HK"
SubElement(channel, "lastBuildDate").text = datetime.now(
    timezone.utc
).strftime("%a, %d %b %Y %H:%M:%S GMT")

count = 0

for news in news_list[:MAX_ITEMS]:
    print("正在抓取:", news["title"])

    summary = get_summary(news["url"], news["title"])

    item = SubElement(channel, "item")
    SubElement(item, "title").text = news["title"]
    SubElement(item, "link").text = news["url"]
    SubElement(item, "guid", isPermaLink="true").text = news["url"]
    SubElement(item, "description").text = summary

    count += 1
    time.sleep(0.3)

ElementTree(rss).write(
    OUTPUT_FILE,
    encoding="utf-8",
    xml_declaration=True
)

print(f"RSS生成成功，共 {count} 条新闻")
