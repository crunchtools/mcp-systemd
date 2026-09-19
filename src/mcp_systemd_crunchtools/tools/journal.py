"""Troubleshooting tools — journal queries, failed units, pending jobs."""

from typing import Any

from ..dbus_client import failed_units as _failed_units
from ..dbus_client import journal_query as _journal_query
from ..dbus_client import list_jobs as _list_jobs


async def journal_query(
    unit: str | None = None,
    priority: str | None = None,
    since: str | None = None,
    until: str | None = None,
    pattern: str | None = None,
    boot: int | None = None,
    lines: int = 100,
) -> dict[str, Any]:
    """Query the journal with optional unit/priority/time/pattern/boot filters."""
    return await _journal_query(
        unit=unit, priority=priority, since=since, until=until,
        pattern=pattern, boot=boot, lines=lines,
    )


async def failed_units() -> dict[str, Any]:
    """List units currently in the 'failed' state."""
    return await _failed_units()


async def list_jobs() -> dict[str, Any]:
    """List pending systemd jobs (starts/stops/reloads in progress or queued)."""
    return await _list_jobs()
