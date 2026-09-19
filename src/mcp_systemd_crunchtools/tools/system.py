"""System-level inspection tools."""

from typing import Any

from ..dbus_client import hostinfo as _hostinfo
from ..dbus_client import system_status as _system_status


async def system_status() -> dict[str, Any]:
    """Get overall systemd manager state (SystemState, failed/job counts, version)."""
    return await _system_status()


async def hostinfo() -> dict[str, Any]:
    """Get host identity info (hostname, kernel, OS)."""
    return await _hostinfo()
