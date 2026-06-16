"""boss doctor — 诊断本地环境、服务器、登录态。"""

from __future__ import annotations

import json
import sys
import time
import urllib.request

import click
from rich.console import Console

EXTENSION_SERVER_URL = "http://127.0.0.1:9876"

console = Console()


@click.command()
def doctor():
    """诊断本地环境"""
    console.print("=== Boss CLI 诊断 ===")
    console.print()

    # Python
    console.print(f"Python: {sys.version.split()[0]}")

    # Cookie 服务器
    try:
        resp = urllib.request.urlopen(f"{EXTENSION_SERVER_URL}/status", timeout=3)
        data = resp.read().decode()
        info = json.loads(data)
        last = info.get("last_sync", 0)
        cookies = info.get("cookies", {})
        console.print("Cookie server: ✅ running")
        if last:
            console.print(f"  Last sync: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last))}")
        if cookies:
            console.print(f"  Cookies: {', '.join(cookies.keys())}")
            has_stoken = "__zp_stoken__" in cookies
            console.print(f"  __zp_stoken__: {'✅' if has_stoken else '❌ missing'}")
        else:
            console.print("  Cookies: none (waiting for extension)")
    except Exception:
        console.print("Cookie server: ❌ not running")
        console.print("  Start with: boss cookie-server start")

    # 登录态
    from ..auth import load_credential
    cred = load_credential()
    if cred and cred.has_required_cookies:
        console.print(f"Credential: ✅ valid ({len(cred.cookies)} cookies)")
    elif cred:
        console.print(f"Credential: ⚠️ partial (missing: {', '.join(cred.missing_required_cookies)})")
    else:
        console.print("Credential: ❌ not found")
