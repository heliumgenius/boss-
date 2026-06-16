"""Recruiter commands: interview management."""
from __future__ import annotations

import click

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

_STOKEN_HINT = (
    "[yellow]\u26a0\ufe0f 此操作需要 __zp_stoken__ (由浏览器 JS 生成)。"
    "请先在浏览器登录后执行 boss login 补全 Cookie。[/yellow]"
)


def _chat_action_hint(exc: BossApiError) -> None:
    """Print an extra stoken recovery hint to stderr if the error looks
    like it was caused by a missing __zp_stoken__ cookie. Intended to be
    passed to ``handle_command(..., error_hint=...)`` so it runs AFTER the
    standard error is printed."""
    msg = str(exc)
    if "缺少必要参数" in msg or "stoken" in msg.lower() or "<" in msg[:5]:
        console.print(f"  {_STOKEN_HINT}")


@recruiter.command("invite-interview")
@click.argument("encrypt_geek_id")
@click.option("--job", "encrypt_job_id", required=True, help="关联职位 encryptJobId")
@click.option("--address", default="", help="面试地点")
@click.option("--time", "start_time", default="", help="面试开始时间")
@click.option("--desc", "description", default="", help="面试说明")
@click.option("-y", "--yes", is_flag=True, help="跳过确认提示")
@structured_output_options
def recruiter_invite_interview(
    encrypt_geek_id: str, encrypt_job_id: str, address: str,
    start_time: str, description: str, yes: bool,
    as_json: bool, as_yaml: bool,
) -> None:
    """邀请候选人面试 (Invite candidate for interview)"""
    cred = require_auth()

    if not yes:
        console.print(f"[cyan]将邀请候选人面试: {encrypt_geek_id}[/cyan]")
        if address:
            console.print(f"  地点: {address}")
        if start_time:
            console.print(f"  时间: {start_time}")
        confirm = click.confirm("确认邀请?")
        if not confirm:
            console.print("[dim]已取消[/dim]")
            return

    security_id = ""
    try:
        friend_data = run_client_action(cred, lambda c: c.get_boss_friend_list())
        for f in friend_data.get("result", []):
            if f.get("encryptFriendId") == encrypt_geek_id:
                detail = run_client_action(
                    cred,
                    lambda c, fid=f["friendId"]: c.get_boss_friend_details([fid]),
                )
                for fd in detail.get("friendList", []):
                    security_id = fd.get("securityId", "")
                    break
                break
    except BossApiError:
        pass

    def _action(c: BossClient) -> dict:
        return c.boss_interview_invite(
            encrypt_geek_id=encrypt_geek_id,
            encrypt_job_id=encrypt_job_id,
            security_id=security_id,
            address=address,
            start_time=start_time,
            description=description,
        )

    def _render(data: dict) -> None:
        console.print(f"[green]已发送面试邀请 -> {encrypt_geek_id}[/green]")

    handle_command(
        cred, action=_action, render=_render,
        as_json=as_json, as_yaml=as_yaml,
        error_hint=_chat_action_hint,
    )
