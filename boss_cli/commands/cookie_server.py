"""boss cookie-server 子命令 — 启动/停止 Cookie 接收服务器。"""

from __future__ import annotations

import json
import time
import urllib.request

import click
from rich.console import Console

SERVER_URL = "http://127.0.0.1:9876"

console = Console()


@click.group()
def cookie_server():
    """Edge Extension Cookie 服务器"""


@cookie_server.command("start")
@click.option("--port", default=9876, type=int, help="监听端口")
@click.option("--foreground", is_flag=True, help="前台运行（默认后台）")
def start(port, foreground):
    """启动 Cookie 服务器"""
    from ..cookie_server import run_server

    run_server(port=port, daemon=not foreground)


@cookie_server.command("stop")
def stop():
    """停止 Cookie 服务器"""
    try:
        req = urllib.request.Request(f"{SERVER_URL}/shutdown", method="GET")
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass
    console.print("Cookie server stopped")


@cookie_server.command("status")
def _status():
    """检查服务器状态"""
    try:
        resp = urllib.request.urlopen(f"{SERVER_URL}/status", timeout=3)
        data = resp.read().decode()
        info = json.loads(data)
        last = info.get("last_sync", 0)
        cookies = info.get("cookies", {})
        console.print("Server: running")
        if last:
            console.print(f"Last sync: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last))}")
        console.print(f"Cookies: {len(cookies)} keys ({', '.join(cookies.keys())})")
    except Exception:
        console.print("Server: not running")
