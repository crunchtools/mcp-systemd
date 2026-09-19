"""Unit inspection tools — list, status, and full property dumps."""

from typing import Any

from ..dbus_client import unit_list as _unit_list
from ..dbus_client import unit_show as _unit_show
from ..dbus_client import unit_status as _unit_status


async def unit_list(
    all_units: bool = False, pattern: str | None = None, mode: str = "loaded",
) -> dict[str, Any]:
    """List systemd units, loaded or installed."""
    return await _unit_list(all_units=all_units, pattern=pattern, mode=mode)


async def unit_status(unit_name: str) -> dict[str, Any]:
    """Get curated status properties for a unit."""
    return await _unit_status(unit_name)


async def unit_show(unit_name: str) -> dict[str, Any]:
    """Dump the full property set for a unit."""
    return await _unit_show(unit_name)
