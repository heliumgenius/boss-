"""Recruiter (Boss) mode command group."""
from __future__ import annotations

import click


@click.group(name="recruiter")
def recruiter() -> None:
    """招聘方/雇主端操作 (Recruiter mode)"""


from . import positions, candidates, interviews, chat
