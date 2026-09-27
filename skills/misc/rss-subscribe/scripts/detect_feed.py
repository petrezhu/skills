#!/usr/bin/env python3
"""探测一个网站的 RSS/Atom 源，输出 JSON 结论。

用法:
    detect_feed.py <站点URL或域名>
    detect_feed.py https://example.com/blog

输出字段:
    status      ok | none | error
    candidates  探测到的候选 feed 列表（按可信度排序）
    recommended 首选 feed URL（无则为 null）
    method      命中的探测手段: link-tag | path-probe
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlparse

UA = "Mozilla/5.0 (compatible; RSSHub-Detect/1.0; +https://rsshub.petrezhu.cn)"
TIMEOUT = 12

# 按出现频率排序的常见 feed 路径
CANDIDATE_PATHS = [
    "/feed",
    "/rss.xml",
    "/atom.xml",
    "/index.xml",
    "/feed.xml",
    "/rss",
    "/atom",
    "/rss/",
    "/feeds/posts/default",
    "/blog/feed",
    "/blog/rss.xml",
    "/posts/index.xml",
    "/.rss",
    # 注意: 不要放 /sitemap.xml。sitemap 是 XML 但不是 feed,
    # 曾被 <?xml 标记误判成原生源, 让「无 RSS 的站」拿到站点地图当订阅。
]

# <link rel="alternate" ...> 抓取
LINK_TAG_RE = re.compile(
    r"""<link[^>]+rel\s*=\s*["']alternate["'][^>]*>""",
    re.IGNORECASE,
)
HREF_RE = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
TYPE_RE = re.compile(r"""type\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
TITLE_RE = re.compile(r"""<title[^>]*>(.*?)</title>""", re.IGNORECASE | re.DOTALL)

FEED_MARKERS = ("<rss", "<feed", "<atom", "<rdf:rss", "<?xml")
# 明确不是 feed 的 XML。sitemap 也以 <?xml 开头, 不加这条会被当成原生源。
NOT_FEED_MARKERS = ("<urlset", "<sitemapindex")

# 站点反爬/限流状态码，这些不是「没有 RSS」，是「探测不到」
BLOCKED_STATUS = {403, 406, 429, 503, 599, 999}


def fetch(url: str) -> tuple[int, str, str]:
    """返回 (status, content_type, body)。body 可能被截断。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read(200_000)
            ctype = resp.headers.get("Content-Type", "")
            return resp.status, ctype, raw.decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read(5_000).decode("utf-8", "replace")
        except Exception:
            pass
        return e.code, "", body
    except Exception:
        return 0, "", ""


def looks_like_feed(body: str) -> bool:
    head = body.lstrip()[:400].lower()
    if any(m in head for m in NOT_FEED_MARKERS):
        return False  # 站点地图 XML, 不是 feed
    return any(m in head for m in FEED_MARKERS)


def probe_link_tags(page_url: str, html: str) -> list[dict]:
    """page_url = 实际抓到 HTML 的那个 URL（不是域名根）。
    feed 的 href 常是相对路径（如 blog 页面里的 atom.xml），
    必须以页面 URL 为基准解析，否则会丢掉 /blog/ 这类前缀。"""
    out = []
    for tag in LINK_TAG_RE.findall(html)[:40]:
        t = TYPE_RE.search(tag)
        if not t:
            continue
        ctype = t.group(1).lower()
        if not any(k in ctype for k in ("rss", "atom", "json")):
            continue
        h = HREF_RE.search(tag)
        if not h:
            continue
        out.append({
            "url": urljoin(page_url, h.group(1)),
            "type": ctype,
            "method": "link-tag",
        })
    return out


def probe_paths(*bases: str) -> list[dict]:
    """在每个 base 下盲探常见 feed 路径。
    调用方应同时传「输入路径所在目录」和「域名根」，
    只探域名根会漏掉 /blog/atom.xml 这种带前缀的 feed。"""
    out = []
    seen = set()
    for base in bases:
        for path in CANDIDATE_PATHS:
            url = urljoin(base.rstrip("/") + "/", path.lstrip("/"))
            if url in seen:
                continue
            seen.add(url)
            status, _, body = fetch(url)
            if status == 200 and looks_like_feed(body):
                out.append({"url": url, "type": "unknown", "method": "path-probe"})
    return out


def feed_title(body: str) -> str | None:
    m = TITLE_RE.search(body)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(1)).strip()[:120] or None


def count_items(body: str) -> int:
    return len(re.findall(r"<item[\s>]", body, re.IGNORECASE)) + len(
        re.findall(r"<entry[\s>]", body, re.IGNORECASE)
    )


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "error": "usage: detect_feed.py <url>"}))
        return 2

    target = sys.argv[1].strip()
    if not urlparse(target).scheme:
        target = "https://" + target
    base = f"{urlparse(target).scheme}://{urlparse(target).netloc}"

    # 页面所在目录：带前缀的 feed（如 /blog/atom.xml）挂在这里，不在域名根
    parsed = urlparse(target)
    page_dir = base + "/" if parsed.path in ("", "/") else (
        target if target.endswith("/") else target.rsplit("/", 1)[0] + "/"
    )

    status, ctype, body = fetch(target)
    if status == 0:
        print(json.dumps({"status": "error", "error": f"cannot fetch {target}", "site": base}, ensure_ascii=False))
        return 1

    # 反爬站点：首页都拿不到，此时不能下「无 RSS」的结论
    if status in BLOCKED_STATUS:
        print(json.dumps({
            "status": "blocked",
            "http_status": status,
            "site": base,
            "error": f"site returned HTTP {status} (anti-bot / rate limit)",
            "hint": "站点反爬，原生探测无效。改用 RSSHub 路由，或经代理/渲染后重试。",
            "native": None,
            "candidates": [],
            "recommended": None,
        }, ensure_ascii=False, indent=2))
        return 4

    # 候选分两轮收集：link-tag 先验，验不出可用的再盲探路径。
    # 不能因为「link-tag 命中」就跳过盲探，命中的可能指向境外
    # 代理服务（如 FeedBurner），从本机根本连不通，会把整站误判成无源。
    found: list[dict] = []
    if "<html" in body[:4000].lower() or not looks_like_feed(body):
        # link-tag 必须以「抓到 HTML 的那个 URL」为基准解析相对 href
        found += probe_link_tags(target, body)
    elif looks_like_feed(body):
        found.append({"url": target, "type": "unknown", "method": "direct"})

    def validate(pool: list[dict]) -> list[dict]:
        out, seen = [], set()
        for c in pool:
            if c["url"] in seen:
                continue
            seen.add(c["url"])
            s, _, b = fetch(c["url"])
            if s != 200 or not looks_like_feed(b):
                continue
            c = dict(c)
            c["title"] = feed_title(b)
            c["item_count"] = count_items(b)
            out.append(c)
        return out

    candidates = validate(found)
    # link-tag 全军覆没 → 补盲探（页面目录 + 域名根）
    if not candidates and "<html" in body[:4000].lower():
        candidates = validate(probe_paths(page_dir, base))

    # 直连可用的排前面：境外代理 feed 往往比不上站点自带的
    # 同级则按条目数降序，推荐项应当是内容最全的那个
    rank = {"direct": 0, "link-tag": 1, "path-probe": 2}
    candidates.sort(key=lambda c: (rank.get(c["method"], 3), -c["item_count"]))

    result = {
        "status": "ok" if candidates else "none",
        "site": base,
        "candidates": candidates,
        "recommended": candidates[0]["url"] if candidates else None,
        "native": bool(candidates),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if candidates else 3


if __name__ == "__main__":
    sys.exit(main())
