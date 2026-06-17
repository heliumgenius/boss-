"""CLI entry point for Boss CLI."""

from __future__ import annotations

import logging
import sys

import click

# Prevent UnicodeEncodeError on Windows GBK terminals when outputting emoji
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')

from . import __version__
from .commands import auth, personal, search, social
from .commands.cookie_server import cookie_server
from .commands.doctor import doctor
from .commands.recruiter import recruiter
from .commands.web_ui import web_ui


@click.group()
@click.version_option(version=__version__, prog_name="boss")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging (show request URLs, timing)")
@click.pass_context
def cli(ctx, verbose: bool) -> None:
    """Boss CLI — 在终端使用 BOSS 直聘 🤝"""
    ctx.ensure_object(dict)
    if verbose:
        logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)


# ─── Auth commands ───────────────────────────────────────────────────

cli.add_command(auth.login)
cli.add_command(auth.logout)
cli.add_command(auth.status)
cli.add_command(auth.me)

# ─── Search & Browse commands ────────────────────────────────────────

cli.add_command(search.search)
cli.add_command(search.recommend)
cli.add_command(search.detail)
cli.add_command(search.show)
cli.add_command(search.export)
cli.add_command(search.history)
cli.add_command(search.cities)

# ─── Personal Center commands ────────────────────────────────────────

cli.add_command(personal.applied)
cli.add_command(personal.interviews)

# ─── Social commands ────────────────────────────────────────────────

cli.add_command(social.chat_list)
cli.add_command(social.greet)
cli.add_command(social.batch_greet)

# ─── Cookie Server commands ─────────────────────────────────────────

cli.add_command(cookie_server)

# ─── Doctor commands ──────────────────────────────────────────────

cli.add_command(doctor)

# ─── Web UI ────────────────────────────────────────────────────────

cli.add_command(web_ui)

# ─── Recruiter (Boss) commands ──────────────────────────────────────

cli.add_command(recruiter)


if __name__ == "__main__":
    cli()
