"""Recruiter commands: job listing management."""
from __future__ import annotations

import json

import click
from rich.table import Table

from ...client.transport import BossClient
from ...exceptions import BossApiError
from .._common import (
    console,
    handle_command,
    require_auth,
    run_client_action,
    structured_output_options,
)

from . import recruiter


@recruiter.command("jobs")
@structured_output_options
def recruiter_jobs(as_json: bool, as_yaml: bool) -> None:
    """查看招聘中的职位列表"""
    cred = require_auth()

    def _render(data: list[dict]) -> None:
        if not data:
            console.print("[yellow]暂无在线职位[/yellow]")
            return

        table = Table(title=f"招聘职位 ({len(data)} 个)", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("职位", style="bold cyan", max_width=25)
        table.add_column("薪资", style="yellow", max_width=12)
        table.add_column("地区", style="blue", max_width=15)
        table.add_column("encJobId", style="dim", max_width=30)

        for i, job in enumerate(data, 1):
            table.add_row(
                str(i),
                job.get("jobName", "-"),
                job.get("salaryDesc", "-"),
                job.get("address", "-"),
                job.get("encryptJobId", "-"),
            )

        console.print(table)
        console.print("  [dim]使用 boss recruiter inbox --job <encJobId> 查看该职位的候选人[/dim]")

    handle_command(
        cred, action=lambda c: c.get_boss_chatted_jobs(),
        render=_render, as_json=as_json, as_yaml=as_yaml,
    )


@recruiter.command("job-close")
@click.argument("encrypt_job_id")
@click.option("-y", "--yes", is_flag=True, help="跳过确认提示")
def recruiter_job_close(encrypt_job_id: str, yes: bool) -> None:
    """关闭/下线职位 (Take job offline)"""
    cred = require_auth()

    if not yes:
        confirm = click.confirm(f"确定关闭职位 {encrypt_job_id}?")
        if not confirm:
            console.print("[dim]已取消[/dim]")
            return

    try:
        result = run_client_action(cred, lambda c: c.boss_job_offline(encrypt_job_id))
        console.print(f"[green]职位已关闭: {encrypt_job_id}[/green]")
        if result:
            console.print(f"  [dim]{json.dumps(result, ensure_ascii=False)[:200]}[/dim]")
    except BossApiError as exc:
        msg = str(exc)
        console.print(f"[red]关闭职位失败: {msg}[/red]")
        if "缺少必要参数" in msg or "stoken" in msg.lower():
            console.print(
                "  [yellow]提示: 该操作可能需要浏览器端 __zp_stoken__ 验证。\n"
                "  请尝试在浏览器中操作, 或重新登录后重试: boss logout && boss login[/yellow]"
            )
        raise SystemExit(1) from None


@recruiter.command("job-reopen")
@click.argument("encrypt_job_id")
@click.option("-y", "--yes", is_flag=True, help="跳过确认提示")
def recruiter_job_reopen(encrypt_job_id: str, yes: bool) -> None:
    """重新开启/上线职位 (Bring job online)"""
    cred = require_auth()

    if not yes:
        confirm = click.confirm(f"确定重新开启职位 {encrypt_job_id}?")
        if not confirm:
            console.print("[dim]已取消[/dim]")
            return

    try:
        result = run_client_action(cred, lambda c: c.boss_job_online(encrypt_job_id))
        console.print(f"[green]职位已开启: {encrypt_job_id}[/green]")
        if result:
            console.print(f"  [dim]{json.dumps(result, ensure_ascii=False)[:200]}[/dim]")
    except BossApiError as exc:
        msg = str(exc)
        console.print(f"[red]开启职位失败: {msg}[/red]")
        if "缺少必要参数" in msg or "stoken" in msg.lower():
            console.print(
                "  [yellow]提示: 该操作可能需要浏览器端 __zp_stoken__ 验证。\n"
                "  请尝试在浏览器中操作, 或重新登录后重试: boss logout && boss login[/yellow]"
            )
        raise SystemExit(1) from None
