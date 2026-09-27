#!/usr/bin/env python3
"""订阅清单管理：登记、列出、验证。

用法:
    subscribe.py add --name 名称 --feed URL [--site URL] [--type native|rsshub] [--note 备注]
    subscribe.py list [--json]
    subscribe.py verify [--limit N] [--name 名称]

清单: <workspace>/data/subscriptions.yaml
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

import rsshub_auth
from detect_feed import FEED_MARKERS, NOT_FEED_MARKERS  # 标记只此一份, 与探测脚本同源

WORKSPACE = os.environ.get(
    "HERMES_WORKSPACE", "/root/.hermes/profiles/main/workspace"
)
MANIFEST = os.path.join(WORKSPACE, "data", "subscriptions.yaml")

UA = "Mozilla/5.0 (compatible; RSSHub-Detect/1.0)"
TIMEOUT = 20
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
ITEM_RE = re.compile(r"<item[\s>]|<entry[\s>]", re.IGNORECASE)
LINK_RE = re.compile(r"<link[^>]*>(.*?)</link>|<link[^>]*href=['\"]([^'\"]+)['\"]", re.IGNORECASE)


def load() -> list[dict]:
    if not os.path.exists(MANIFEST):
        return []
    try:
        import yaml  # type: ignore
    except ImportError:
        return _load_flat()
    with open(MANIFEST, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("subscriptions", []) or []


def _load_flat() -> list[dict]:
    """无 pyyaml 时的极简解析（只认本文件自己写的结构）。"""
    items, cur = [], None
    for line in open(MANIFEST, encoding="utf-8"):
        s = line.rstrip("\n")
        if s.startswith("- name:"):
            cur = {"name": _val(s)}
            items.append(cur)
        elif cur is not None and re.match(r"^\s{4}\w+:", s):
            k, _, v = s.strip().partition(":")
            cur[k] = _val(v)
    return items


def _val(s: str) -> str:
    return s.partition(":")[2].strip().strip('"').strip("'")


def save(items: list[dict]) -> None:
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    lines = [
        "# RSS 订阅清单：由 rss-subscribe skill 维护",
        f"# 更新: {datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}",
        "subscriptions:",
    ]
    for it in items:
        lines.append(f'  - name: "{it.get("name", "")}"')
        for k in ("type", "feed", "site", "note", "added", "last_check", "item_count"):
            if it.get(k) not in (None, ""):
                lines.append(f'    {k}: "{it[k]}"')
    with open(MANIFEST, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def probe(feed_url: str) -> dict:
    headers = {"User-Agent": UA}
    headers.update(rsshub_auth.auth_headers(feed_url))  # rsshub 反代要凭据, 否则 401
    req = urllib.request.Request(feed_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read(300_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return {"ok": False, "error": rsshub_auth.unauthorized_message(feed_url)}
        return {"ok": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    head = body.lstrip()[:400].lower()
    if any(m in head for m in NOT_FEED_MARKERS):
        return {"ok": False, "error": "response is a sitemap, not a feed"}
    if not any(m in head for m in FEED_MARKERS):
        return {"ok": False, "error": "response is not a feed (no RSS/Atom markers)"}

    title = TITLE_RE.search(body)
    return {
        "ok": True,
        "title": re.sub(r"\s+", " ", title.group(1)).strip()[:120] if title else None,
        "items": len(ITEM_RE.findall(body)),
    }


def cmd_add(a) -> int:
    items = load()
    feed = a.feed
    if any(i.get("feed") == feed for i in items):
        print(json.dumps({"status": "exists", "feed": feed}, ensure_ascii=False))
        return 0
    r = probe(feed)
    if not r.get("ok"):
        # 验证不通过就拒收, 没有绕过开关: 入册的必须是实测能拉到条目的源
        print(json.dumps({"status": "rejected", "feed": feed, "reason": r.get("error")},
                         ensure_ascii=False, indent=2))
        return 1
    items.append({
        "name": a.name,
        "type": a.type,
        "feed": feed,
        "site": a.site or "",
        "note": a.note or "",
        "added": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M"),
        "last_check": "",
        "item_count": str(r.get("items", "")),
    })
    save(items)
    print(json.dumps({"status": "added", "name": a.name, "feed": feed,
                      "verified": r.get("ok"), "items": r.get("items"),
                      "feed_title": r.get("title")}, ensure_ascii=False, indent=2))
    return 0


def cmd_list(a) -> int:
    items = load()
    if a.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0
    if not items:
        print("(清单为空)")
        return 0
    print(f"{'名称':<22} {'类型':<8} {'条目':>5}  Feed")
    print("-" * 96)
    for i in items:
        print(f"{i.get('name',''):<22} {i.get('type',''):<8} "
              f"{str(i.get('item_count','')):>5}  {i.get('feed','')}")
    print(f"\n共 {len(items)} 项  →  {MANIFEST}")
    return 0


def cmd_verify(a) -> int:
    all_items = load()
    # 过滤只决定「本轮验证哪些」, 副作用仍作用在 all_items 的同一批 dict 上;
    # 保存必须存 all_items。存 targets 会把清单截断成子集, 直接丢数据。
    targets = all_items
    if a.name:
        targets = [i for i in targets if i.get("name") == a.name]
    if a.limit:
        targets = targets[: a.limit]
    if not targets:
        print("(无待验证项)")
        return 0

    results, changed = [], False
    for it in targets:
        r = probe(it.get("feed", ""))
        entry = {
            "name": it.get("name"), "ok": r.get("ok"),
            "items": r.get("items"), "error": r.get("error"),
        }
        results.append(entry)
        if r.get("ok"):
            it["last_check"] = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
            if r.get("items") is not None:
                it["item_count"] = str(r["items"])
            changed = True
    if changed:
        save(all_items)  # 存完整清单, 不是被 --name/--limit 过滤后的子集
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(x["ok"] for x in results) else 1


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("add")
    pa.add_argument("--name", required=True)
    pa.add_argument("--feed", required=True)
    pa.add_argument("--site", default="")
    pa.add_argument("--type", default="native", choices=["native", "rsshub"])
    pa.add_argument("--note", default="")
    pa.set_defaults(func=cmd_add)

    pl = sub.add_parser("list")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_list)

    pv = sub.add_parser("verify")
    pv.add_argument("--limit", type=int, default=0)
    pv.add_argument("--name", default="")
    pv.set_defaults(func=cmd_verify)

    a = p.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
