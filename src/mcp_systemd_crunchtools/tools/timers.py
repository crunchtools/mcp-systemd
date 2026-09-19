"""Timer inspection tools."""

from typing import Any

from ..dbus_client import timer_list as _timer_list


async def timer_list() -> dict[str, Any]:
    """List systemd timers with their next and last elapse times."""
    return await _timer_list()
