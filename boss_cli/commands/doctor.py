"""boss doctor — 诊断本地环境、服务器、登录态。"""

from __future__ import annotations

import time
import urllib.request

import click

EXTENSION_SERVER_URL = "http://127.0.0.1:9876"


@click.command()
def doctor():
    """诊断本地环境"""
    click.echo("=== Boss CLI 诊断 ===\n")

    # Python
    import sys
    click.echo(f"Python: {sys.version.split()[0]}")

    # Cookie 服务器
    try:
        resp = urllib.request.urlopen(f"{EXTENSION_SERVER_URL}/status", timeout=3)
        data = resp.read().decode()
        import json
        info = json.loads(data)
        last = info.get("last_sync", 0)
        cookies = info.get("cookies", {})
        click.echo("Cookie server: [OK] running")
        if last:
            click.echo(f"  Last sync: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last))}")
        if cookies:
            click.echo(f"  Cookies: {', '.join(cookies.keys())}")
            has_stoken = "__zp_stoken__" in cookies
            click.echo(f"  __zp_stoken__: [{'OK' if has_stoken else 'MISS'}]")
        else:
            click.echo("  Cookies: none (waiting for extension)")
    except Exception:
        click.echo("Cookie server: [--] not running")
        click.echo("  Start with: boss cookie-server start")

    # 登录态
    from ..auth import load_credential
    cred = load_credential()
    if cred and cred.has_required_cookies:
        click.echo(f"Credential: [OK] valid ({len(cred.cookies)} cookies)")
    elif cred:
        click.echo(f"Credential: [WARN] partial (missing: {', '.join(cred.missing_required_cookies)})")
    else:
        click.echo("Credential: [--] not found")
