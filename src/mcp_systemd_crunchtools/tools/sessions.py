"""Login session inspection tools."""

from typing import Any

from ..dbus_client import session_list as _session_list


async def session_list() -> dict[str, Any]:
    """List logged-in sessions (who's on this box)."""
    return await _session_list()
