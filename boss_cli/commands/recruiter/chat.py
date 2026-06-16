"""Recruiter commands: messaging & communication actions."""
from __future__ import annotations

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
from .candidates import _resolve_friend_uid_and_job

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


@recruiter.command("inbox")
@click.option("--job", "enc_job_id", default="", help="按职位 encryptJobId 筛选")
@click.option("--label", "label_id", default=0, type=int, help="按标签筛选 (0=全部, 1=新招呼, 2=沟通中)")
@click.option("-n", "--limit", "display_limit", default=0, type=int, help="显示数量 (0=全部)")
@structured_output_options
def recruiter_inbox(enc_job_id: str, label_id: int, display_limit: int, as_json: bool, as_yaml: bool) -> None:
    """查看候选人消息列表 (招聘方沟通列表)"""
    cred = require_auth()

    def _action(c: BossClient) -> dict:
        friend_data = c.get_boss_friend_list(label_id=label_id, enc_job_id=enc_job_id)
        friend_list = friend_data.get("result", [])

        if not friend_list:
            return {"friendList": [], "lastMessages": []}

        friend_ids = [f["friendId"] for f in friend_list if f.get("friendId")]

        details = c.get_boss_friend_details(friend_ids)
        detail_list = details.get("friendList", [])

        batch_ids = friend_ids[:50]
        last_msgs = c.get_boss_last_messages(batch_ids)

        return {"friendList": detail_list, "lastMessages": last_msgs}

    def _render(data: dict) -> None:
        detail_list = data.get("friendList", [])
        last_msgs = data.get("lastMessages", [])

        if not detail_list:
            console.print("[yellow]暂无候选人消息[/yellow]")
            return

        msg_map: dict[int, dict] = {}
        if isinstance(last_msgs, list):
            for msg in last_msgs:
                uid = msg.get("uid", 0)
                if uid:
                    msg_map[uid] = msg

        total = len(detail_list)
        if display_limit > 0:
            detail_list = detail_list[:display_limit]

        table = Table(title=f"候选人列表 (显示 {len(detail_list)}/{total} 人)", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("候选人", style="bold cyan", max_width=12)
        table.add_column("职位", style="green", max_width=20)
        table.add_column("薪资", style="yellow", max_width=10)
        table.add_column("最近消息", style="dim", max_width=30)
        table.add_column("时间", style="dim", max_width=8)

        for i, friend in enumerate(detail_list, 1):
            uid = friend.get("uid", 0)
            msg_info = msg_map.get(uid, {})
            last_text = ""
            if msg_info.get("lastMsgInfo"):
                last_text = msg_info["lastMsgInfo"].get("showText", "")[:28]

            table.add_row(
                str(i),
                friend.get("name", "-"),
                friend.get("jobName", "-"),
                friend.get("salaryDesc", friend.get("lastTime", "-")),
                last_text or "-",
                msg_info.get("lastTime", friend.get("lastTime", "-")),
            )

        console.print(table)
        console.print("  [dim]使用 boss recruiter resume <encryptGeekId> 查看候选人简历[/dim]")
        console.print("  [dim]💡 限制显示: boss recruiter inbox -n 20[/dim]")
        console.print("  [dim]   按标签筛选: boss recruiter inbox --label 1 (1=新招呼, 2=沟通中)[/dim]")

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


@recruiter.command("reply")
@click.argument("friend_id", type=int)
@click.argument("message")
@click.option("-y", "--yes", is_flag=True, help="跳过确认提示")
@structured_output_options
def recruiter_reply(friend_id: int, message: str, yes: bool, as_json: bool, as_yaml: bool) -> None:
    """发送消息给候选人 (Send message to candidate)"""
    cred = require_auth()

    if not yes:
        console.print(f"[cyan]将向 friendId={friend_id} 发送消息:[/cyan]")
        console.print(f"  {message}")
        confirm = click.confirm("\n确认发送?")
        if not confirm:
            console.print("[dim]已取消[/dim]")
            return

    def _action(c: BossClient) -> dict:
        return c.boss_send_message(gid=friend_id, content=message)

    def _render(data: dict) -> None:
        console.print(f"[green]消息已发送 -> friendId={friend_id}[/green]")

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


@recruiter.command("chat")
@click.argument("friend_id", type=int)
@click.option("-n", "--count", default=20, type=int, help="消息数量 (默认: 20)")
@structured_output_options
def recruiter_chat(friend_id: int, count: int, as_json: bool, as_yaml: bool) -> None:
    """查看与候选人的聊天记录 (需要 friendId)"""
    cred = require_auth()

    def _action(c: BossClient) -> dict:
        return c.get_boss_chat_history(gid=friend_id, count=count)

    def _render(data: dict) -> None:
        messages = data.get("messages", [])

        if not messages:
            console.print("[yellow]暂无聊天记录[/yellow]")
            return

        table = Table(title=f"聊天记录 ({len(messages)} 条)", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("方向", max_width=6)
        table.add_column("内容", max_width=50)
        table.add_column("类型", style="dim", max_width=6)

        for i, msg in enumerate(messages, 1):
            direction = "[cyan]<-[/cyan]" if msg.get("received", True) else "[green]->[/green]"

            body = msg.get("body", {})
            if isinstance(body, str):
                text = body[:48]
            elif isinstance(body, dict):
                text = body.get("text", body.get("showText", ""))
                if not text and body.get("resume"):
                    resume = body["resume"]
                    text = f"[简历] {resume.get('user', {}).get('name', '')} {resume.get('positionCategory', '')}"
                text = text[:48] if text else "[多媒体消息]"
            else:
                text = str(body)[:48]

            msg_type = str(msg.get("type", "-"))

            table.add_row(str(i), direction, text, msg_type)

        console.print(table)
        console.print(f"  [dim]加载更多: boss recruiter chat {friend_id} -n {count + 20}[/dim]")

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


@recruiter.command("request-resume")
@click.argument("friend_id", type=int)
@click.option("-y", "--yes", is_flag=True, help="跳过确认提示")
@structured_output_options
def recruiter_request_resume(friend_id: int, yes: bool, as_json: bool, as_yaml: bool) -> None:
    """向候选人请求简历 (Request resume from candidate)"""
    cred = require_auth()

    if not yes:
        console.print(f"[cyan]将向 friendId={friend_id} 请求简历[/cyan]")
        confirm = click.confirm("确认请求?")
        if not confirm:
            console.print("[dim]已取消[/dim]")
            return

    uid, job_id = _resolve_friend_uid_and_job(cred, friend_id)

    def _action(c: BossClient) -> dict:
        return c.boss_exchange_request(uid=uid, job_id=job_id, exchange_type=3)

    def _render(data: dict) -> None:
        console.print(f"[green]已向候选人请求简历 (friendId={friend_id}, uid={uid})[/green]")

    handle_command(
        cred, action=_action, render=_render,
        as_json=as_json, as_yaml=as_yaml,
        error_hint=_chat_action_hint,
    )


@recruiter.command("exchange-phone")
@click.argument("friend_id", type=int)
@click.option("-y", "--yes", is_flag=True, help="跳过确认提示")
@structured_output_options
def recruiter_exchange_phone(friend_id: int, yes: bool, as_json: bool, as_yaml: bool) -> None:
    """交换候选人手机号 (Exchange phone number with candidate)"""
    cred = require_auth()

    if not yes:
        console.print(f"[cyan]将与 friendId={friend_id} 交换手机号[/cyan]")
        confirm = click.confirm("确认交换?")
        if not confirm:
            console.print("[dim]已取消[/dim]")
            return

    uid, job_id = _resolve_friend_uid_and_job(cred, friend_id)

    def _action(c: BossClient) -> dict:
        return c.boss_exchange_request(uid=uid, job_id=job_id, exchange_type=1)

    def _render(data: dict) -> None:
        console.print(f"[green]已向候选人请求交换手机号 (friendId={friend_id}, uid={uid})[/green]")

    handle_command(
        cred, action=_action, render=_render,
        as_json=as_json, as_yaml=as_yaml,
        error_hint=_chat_action_hint,
    )


@recruiter.command("exchange-wechat")
@click.argument("friend_id", type=int)
@click.option("-y", "--yes", is_flag=True, help="跳过确认提示")
@structured_output_options
def recruiter_exchange_wechat(friend_id: int, yes: bool, as_json: bool, as_yaml: bool) -> None:
    """交换候选人微信 (Exchange WeChat with candidate)"""
    cred = require_auth()

    if not yes:
        console.print(f"[cyan]将与 friendId={friend_id} 交换微信[/cyan]")
        confirm = click.confirm("确认交换?")
        if not confirm:
            console.print("[dim]已取消[/dim]")
            return

    uid, job_id = _resolve_friend_uid_and_job(cred, friend_id)

    def _action(c: BossClient) -> dict:
        return c.boss_exchange_request(uid=uid, job_id=job_id, exchange_type=2)

    def _render(data: dict) -> None:
        console.print(f"[green]已向候选人请求交换微信 (friendId={friend_id}, uid={uid})[/green]")

    handle_command(
        cred, action=_action, render=_render,
        as_json=as_json, as_yaml=as_yaml,
        error_hint=_chat_action_hint,
    )


@recruiter.command("mark-unsuitable")
@click.argument("encrypt_geek_id")
@click.option("--job", "encrypt_job_id", required=True, help="关联职位 encryptJobId")
@click.option("-y", "--yes", is_flag=True, help="跳过确认提示")
@structured_output_options
def recruiter_mark_unsuitable(
    encrypt_geek_id: str, encrypt_job_id: str, yes: bool,
    as_json: bool, as_yaml: bool,
) -> None:
    """标记候选人不合适 (Mark candidate as unsuitable)"""
    cred = require_auth()

    if not yes:
        console.print(f"[cyan]将标记候选人为不合适: {encrypt_geek_id}[/cyan]")
        confirm = click.confirm("确认标记?")
        if not confirm:
            console.print("[dim]已取消[/dim]")
            return

    def _action(c: BossClient) -> dict:
        return c.boss_mark_unsuitable(
            encrypt_geek_id=encrypt_geek_id,
            encrypt_job_id=encrypt_job_id,
        )

    def _render(data: dict) -> None:
        console.print(f"[green]已标记候选人为不合适 -> {encrypt_geek_id}[/green]")

    handle_command(
        cred, action=_action, render=_render,
        as_json=as_json, as_yaml=as_yaml,
        error_hint=_chat_action_hint,
    )
