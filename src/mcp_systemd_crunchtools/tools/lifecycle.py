"""Unit lifecycle tools — start/stop/restart/reload, enable/disable, mask/unmask."""

from typing import Any

from ..dbus_client import daemon_reload as _daemon_reload
from ..dbus_client import unit_disable as _unit_disable
from ..dbus_client import unit_enable as _unit_enable
from ..dbus_client import unit_mask as _unit_mask
from ..dbus_client import unit_reload as _unit_reload
from ..dbus_client import unit_restart as _unit_restart
from ..dbus_client import unit_start as _unit_start
from ..dbus_client import unit_stop as _unit_stop
from ..dbus_client import unit_unmask as _unit_unmask


async def unit_start(unit_name: str) -> dict[str, Any]:
    """Start a unit."""
    return await _unit_start(unit_name)


async def unit_stop(unit_name: str) -> dict[str, Any]:
    """Stop a unit."""
    return await _unit_stop(unit_name)


async def unit_restart(unit_name: str) -> dict[str, Any]:
    """Restart a unit."""
    return await _unit_restart(unit_name)


async def unit_reload(unit_name: str) -> dict[str, Any]:
    """Ask a unit to reload its configuration without restarting."""
    return await _unit_reload(unit_name)


async def unit_enable(unit_name: str) -> dict[str, Any]:
    """Enable a unit to start on boot."""
    return await _unit_enable(unit_name)


async def unit_disable(unit_name: str) -> dict[str, Any]:
    """Disable a unit from starting on boot."""
    return await _unit_disable(unit_name)


async def unit_mask(unit_name: str) -> dict[str, Any]:
    """Mask a unit so it cannot be started even manually."""
    return await _unit_mask(unit_name)


async def unit_unmask(unit_name: str) -> dict[str, Any]:
    """Unmask a previously masked unit."""
    return await _unit_unmask(unit_name)


async def daemon_reload() -> dict[str, Any]:
    """Reload systemd's unit file cache."""
    return await _daemon_reload()
