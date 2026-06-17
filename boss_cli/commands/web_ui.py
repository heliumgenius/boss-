"""boss web-ui 命令 — 启动 Web 界面。"""

from __future__ import annotations

import click
from rich.console import Console

console = Console()


@click.command()
@click.option("--port", default=8080, type=int, help="监听端口 (默认: 8080)")
@click.option("--host", default="127.0.0.1", help="监听地址 (默认: 127.0.0.1)")
def web_ui(port: int, host: str) -> None:
    """启动 Web 界面 (浏览器访问 http://127.0.0.1:8080)"""
    import uvicorn
    from ..web_ui.app import app
    console.print(f"[green]Web UI 启动: http://{host}:{port}[/green]")
    console.print("  按 Ctrl+C 停止")
    uvicorn.run(app, host=host, port=port)
