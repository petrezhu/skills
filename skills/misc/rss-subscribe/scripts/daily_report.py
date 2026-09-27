#!/usr/bin/env python3
"""生成订阅日报：读清单 → 拉各 feed → 汇总最新条目。

用法:
    daily_report.py [--limit N] [--feed 条数] [--markdown]

设计说明（Q3=C：先手动触发，不挂定时）:
    暂不做已读去重，当前输出「各源最新 N 条」，供人工扫读。
    加定时/去重属另一环节，归 blogwatcher。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

import rsshub_auth
from subscribe import load as _load_manifest  # 清单解析只此一份

# 安全：feed 来自第三方站点（不可信输入），stdlib ElementTree 默认对
# XXE / entity-expansion(billion laughs) 无防护，必须用 defusedxml。
# 检测脚本 detect_feed.py 只做正则匹配、不解析 XML，故无需此处理。
try:
    from defusedxml.ElementTree import fromstring as _xml_fromstring
    from defusedxml.common import DefusedXmlException as _UnsafeXMLError
except ImportError:
    # 降级到 stdlib：解析照常，但对 XXE/实体膨胀不再有防护。
    # 不在输出里加标注（属未经请求的 UI 改动），缺依赖时此处静默降级。
    from xml.etree.ElementTree import fromstring as _xml_fromstring, ParseError as _UnsafeXMLError

WORKSPACE = os.environ.get("HERMES_WORKSPACE", "/root/.hermes/profiles/main/workspace")
MANIFEST = os.path.join(WORKSPACE, "data", "subscriptions.yaml")

UA = "Mozilla/5.0 (compatible; RSSHub-Detect/1.0)"
TIMEOUT = 30
ITEM_TAGS = ("item", "entry")


def load_subs() -> list[dict]:
    """读订阅清单。与 subscribe.py 共用同一实现，避免两份解析逻辑漂移。"""
    return _load_manifest()


def strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def parse_feed(body: str, limit: int) -> list[dict]:
    try:
        root = _xml_fromstring(body)
    except _UnsafeXMLError:
        # 格式错误，或 defusedxml 拦下了 XXE / 实体膨胀攻击
        return []
    out = []
    for el in root.iter():
        if strip_ns(el.tag) not in ITEM_TAGS:
            continue
        rec: dict = {"title": "", "link": "", "date": "", "summary": ""}
        for child in el:
            t = strip_ns(child.tag)
            text = (child.text or "").strip()
            if t == "title":
                rec["title"] = re.sub(r"\s+", " ", text)[:160]
            elif t == "link":
                rec["link"] = (child.text or "").strip() or child.get("href", "")
            elif t in ("pubdate", "date", "updated", "published"):
                rec["date"] = text[:31]
            elif t in ("description", "summary", "content"):
                if not rec["summary"]:
                    rec["summary"] = re.sub(r"<[^>]+>", " ", text)
                    rec["summary"] = re.sub(r"\s+", " ", rec["summary"]).strip()[:200]
        if rec["title"] or rec["link"]:
            out.append(rec)
        if len(out) >= limit:
            break
    return out


def fetch(url: str) -> str:
    headers = {"User-Agent": UA}
    headers.update(rsshub_auth.auth_headers(url))  # rsshub 反代要凭据, 否则 401
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read(400_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise RuntimeError(rsshub_auth.unauthorized_message(url)) from None
        raise RuntimeError(f"HTTP {e.code}") from None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0, help="只取前 N 个订阅源")
    p.add_argument("--feed", type=int, default=3, help="每个源取几条")
    p.add_argument("--markdown", action="store_true", help="输出 Markdown")
    args = p.parse_args()

    subs = load_subs()
    if args.limit:
        subs = subs[: args.limit]
    if not subs:
        print("订阅清单为空。用 subscribe.py add 先入册。")
        return 1

    now = datetime.now(timezone.utc).astimezone()
    md = args.markdown
    lines = []
    lines.append(f"# 订阅日报 {now.strftime('%Y-%m-%d %H:%M')}" if md
                 else f"订阅日报 {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    ok = fail = 0
    for s in subs:
        name, url = s.get("name", "?"), s.get("feed", "")
        try:
            items = parse_feed(fetch(url), args.feed)
            ok += 1
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                OSError, RuntimeError) as e:
            fail += 1
            reason = getattr(e, "reason", e)
            lines.append((f"## ✗ {name}" if md else f"✗ {name}"))
            lines.append((f"- 拉取失败：`{reason}`" if md else f"    失败: {reason}"))
            lines.append("")
            continue

        lines.append(f"## {name}" if md else f"■ {name}")
        if not items:
            lines.append("- 该源当前无条目" if md else "    （无条目）")
        for it in items:
            title = it["title"] or "(无标题)"
            date = it["date"][:16]
            if md:
                row = f"- **{title}**"
                if date:
                    row += f"  <sub>{date}</sub>"
                if it["link"]:
                    row += f" · [链接]({it['link']})"
                lines.append(row)
                if it["summary"]:
                    lines.append(f"  > {it['summary']}")
            else:
                lines.append(f"    • {date}  {title}")
                if it["link"]:
                    lines.append(f"      {it['link']}")
        lines.append("")

    lines.append(f"---")
    lines.append(f"共 {len(subs)} 个源：{ok} 成功 / {fail} 失败")
    print("\n".join(lines))
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
