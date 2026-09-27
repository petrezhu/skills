#!/usr/bin/env python3
"""RSSHub 反代的 Basic Auth 凭据读取。

只有 rss.petrezhu.cn 需要认证；其余原生 feed 不带任何凭据。

凭据存本地文件，绝不写进清单、绝不进对话、绝不进 git。
"""
from __future__ import annotations

import base64
import os

# 持久位置。不要放 cache/scratch（24h 空闲会被清理，届时所有 rsshub 源静默 401）
CRED_FILE = os.environ.get(
    "RSSHUB_CRED_FILE",
    "/root/.hermes/profiles/main/secrets/rsshub-basic-auth",
)
RSSHUB_HOST = "rss.petrezhu.cn"


def _read_pair() -> tuple[str, str]:
    """读 '账号: xxx' / '密码: yyy' 两行。读不到返回空串。"""
    try:
        with open(CRED_FILE, encoding="utf-8") as f:
            user = pw = ""
            for line in f:
                if line.startswith("账号:"):
                    user = line.partition(":")[2].strip()
                elif line.startswith("密码:"):
                    pw = line.partition(":")[2].strip()
            return user, pw
    except OSError:
        return "", ""


def auth_headers(url: str) -> dict[str, str]:
    """返回该 URL 需要的请求头。非 RSSHub 地址返回空 dict。"""
    if RSSHUB_HOST not in url:
        return {}
    user, pw = _read_pair()
    if not (user and pw):
        return {}
    token = base64.b64encode(f"{user}:{pw}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def missing() -> bool:
    """凭据文件缺失或不完整时为 True（供调用方给出可操作的提示）。"""
    user, pw = _read_pair()
    return not (user and pw)


def unauthorized_message(url: str) -> str:
    """401 时的可读说明。凭据缺失要指路，凭据错误要区分，两者都不可只报数字码。

    两个调用方（subscribe 返回 dict、daily_report 抛异常）只是错误出口不同，
    说明文案必须一致，所以收在这里。
    """
    if not (RSSHUB_HOST in url):
        return "HTTP 401 unauthorized"
    hint = f"凭据缺失: {CRED_FILE}" if missing() else "凭据错误"
    return f"HTTP 401 unauthorized（{hint}）"
