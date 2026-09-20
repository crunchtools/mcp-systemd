"""FastMCP server setup for systemd MCP."""

import logging
from typing import Any

from fastmcp import FastMCP

from .tools import (
    daemon_reload,
    failed_units,
    hostinfo,
    journal_query,
    list_jobs,
    session_list,
    system_status,
    timer_list,
    unit_disable,
    unit_enable,
    unit_file_remove,
    unit_file_write,
    unit_list,
    unit_mask,
    unit_reload,
    unit_restart,
    unit_show,
    unit_start,
    unit_status,
    unit_stop,
    unit_unmask,
)

logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="mcp-systemd-crunchtools",
    version="0.1.0",
    instructions=(
        "MCP server for systemd unit management via D-Bus. Manages the full "
        "lifecycle of any systemd unit — not just Podman-managed containers: "
        "listing, status, start/stop/restart/reload, enable/disable/mask, "
        "writing and decommissioning unit files, journal queries, failed-unit "
        "and pending-job triage, timers, host info, and login sessions. "
        "A small denylist of core system units (dbus, sshd, networking, "
        "logind) cannot be stopped, disabled, masked, or removed."
    ),
)


@mcp.tool()
async def unit_list_tool(
    all_units: bool = False, pattern: str | None = None, mode: str = "loaded",
) -> dict[str, Any]:
    """List systemd units.

    Args:
        all_units: Include inactive/dead units (default shows only active/failed)
        pattern: Glob pattern to filter unit names (e.g. "mcp-*.service")
        mode: "loaded" for units currently loaded in memory, "files" for all
            installed unit files (includes units not currently loaded)

    Returns:
        List of units (or unit files) with count
    """
    return await unit_list(all_units=all_units, pattern=pattern, mode=mode)


@mcp.tool()
async def unit_status_tool(unit_name: str) -> dict[str, Any]:
    """Get curated status for a unit: active/sub/load state, PID, memory, CPU.

    Args:
        unit_name: Systemd unit name (e.g. "acquacotta.crunchtools.com.service")

    Returns:
        Curated unit properties
    """
    return await unit_status(unit_name)


@mcp.tool()
async def unit_show_tool(unit_name: str) -> dict[str, Any]:
    """Dump the full property set for a unit (dependencies, exec settings, cgroup, etc).

    Args:
        unit_name: Systemd unit name

    Returns:
        Full property dictionary from the Unit and type-specific D-Bus interfaces
    """
    return await unit_show(unit_name)


@mcp.tool()
async def unit_start_tool(unit_name: str) -> dict[str, Any]:
    """Start a unit.

    Args:
        unit_name: Systemd unit name

    Returns:
        Start confirmation
    """
    return await unit_start(unit_name)


@mcp.tool()
async def unit_stop_tool(unit_name: str) -> dict[str, Any]:
    """Stop a unit. Refused for units on the protected list.

    Args:
        unit_name: Systemd unit name

    Returns:
        Stop confirmation
    """
    return await unit_stop(unit_name)


@mcp.tool()
async def unit_restart_tool(unit_name: str) -> dict[str, Any]:
    """Restart a unit. Refused for units on the protected list.

    Args:
        unit_name: Systemd unit name

    Returns:
        Restart confirmation
    """
    return await unit_restart(unit_name)


@mcp.tool()
async def unit_reload_tool(unit_name: str) -> dict[str, Any]:
    """Ask a unit to reload its configuration without restarting.

    Args:
        unit_name: Systemd unit name

    Returns:
        Reload confirmation
    """
    return await unit_reload(unit_name)


@mcp.tool()
async def unit_enable_tool(unit_name: str) -> dict[str, Any]:
    """Enable a unit to start on boot.

    Args:
        unit_name: Systemd unit name

    Returns:
        Enable confirmation with the symlink changes made
    """
    return await unit_enable(unit_name)


@mcp.tool()
async def unit_disable_tool(unit_name: str) -> dict[str, Any]:
    """Disable a unit from starting on boot. Refused for units on the protected list.

    Args:
        unit_name: Systemd unit name

    Returns:
        Disable confirmation with the symlink changes made
    """
    return await unit_disable(unit_name)


@mcp.tool()
async def unit_mask_tool(unit_name: str) -> dict[str, Any]:
    """Mask a unit so it cannot be started even manually. Refused for protected units.

    Args:
        unit_name: Systemd unit name

    Returns:
        Mask confirmation
    """
    return await unit_mask(unit_name)


@mcp.tool()
async def unit_unmask_tool(unit_name: str) -> dict[str, Any]:
    """Unmask a previously masked unit.

    Args:
        unit_name: Systemd unit name

    Returns:
        Unmask confirmation
    """
    return await unit_unmask(unit_name)


@mcp.tool()
async def daemon_reload_tool() -> dict[str, Any]:
    """Reload systemd's unit file cache (equivalent to systemctl daemon-reload).

    Returns:
        Reload confirmation
    """
    return await daemon_reload()


@mcp.tool()
async def unit_file_write_tool(
    unit_name: str, content: str, enable: bool = False, start: bool = False,
) -> dict[str, Any]:
    """Write a new unit file for setting up a service. Backs up any file it overwrites.

    Requires the host's unit directory (default /etc/systemd/system) to be
    bind-mounted into the container. Runs daemon-reload after writing.

    Args:
        unit_name: Bare unit file name (e.g. "myapp.service")
        content: Full contents of the unit file
        enable: Enable the unit after writing
        start: Start the unit after writing

    Returns:
        Path written, backup path (if one was made), and enable/start results
    """
    return await unit_file_write(unit_name, content, enable=enable, start=start)


@mcp.tool()
async def unit_file_remove_tool(unit_name: str, mask: bool = False) -> dict[str, Any]:
    """Decommission a unit: stop, disable, optionally mask, back up and remove its file.

    Refused for units on the protected list. Best-effort on stop/disable — a
    unit that's already stopped or was never enabled doesn't block file removal.

    Args:
        unit_name: Bare unit file name
        mask: Also mask the unit so nothing can start it again by mistake

    Returns:
        Summary of each step performed and the backup path
    """
    return await unit_file_remove(unit_name, mask=mask)


@mcp.tool()
async def journal_query_tool(
    unit: str | None = None,
    priority: str | None = None,
    since: str | None = None,
    until: str | None = None,
    pattern: str | None = None,
    boot: int | None = None,
    lines: int = 100,
) -> dict[str, Any]:
    """Query the journal — the main 2AM troubleshooting tool.

    Args:
        unit: Restrict to one unit (omit for the whole system journal)
        priority: Minimum priority: emerg/alert/crit/err/warning/notice/info/debug or 0-7
        since: Show entries since this time (e.g. "1 hour ago", "YYYY-MM-DD HH:MM:SS")
        until: Show entries until this time
        pattern: Filter messages by regex pattern (journalctl -g)
        boot: Boot offset (0 = current boot, -1 = previous boot, ...)
        lines: Number of log lines to return (default: 100)

    Returns:
        Journal log output
    """
    return await journal_query(
        unit=unit, priority=priority, since=since, until=until,
        pattern=pattern, boot=boot, lines=lines,
    )


@mcp.tool()
async def failed_units_tool() -> dict[str, Any]:
    """List units currently in the 'failed' state — the first thing to check at 2AM.

    Returns:
        List of failed units with count
    """
    return await failed_units()


@mcp.tool()
async def list_jobs_tool() -> dict[str, Any]:
    """List pending systemd jobs — reveals stuck starts/stops/reloads.

    Returns:
        List of pending jobs with count
    """
    return await list_jobs()


@mcp.tool()
async def timer_list_tool() -> dict[str, Any]:
    """List systemd timers with their next and last elapse times.

    Returns:
        List of timers with count
    """
    return await timer_list()


@mcp.tool()
async def system_status_tool() -> dict[str, Any]:
    """Get overall systemd manager state: running/degraded, failed and job counts.

    Returns:
        SystemState, Version, NFailedUnits, NJobs, NNames
    """
    return await system_status()


@mcp.tool()
async def hostinfo_tool() -> dict[str, Any]:
    """Get host identity info: hostname, kernel, OS.

    Returns:
        Hostname, kernel, and OS details
    """
    return await hostinfo()


@mcp.tool()
async def session_list_tool() -> dict[str, Any]:
    """List logged-in sessions — who's on this box right now.

    Returns:
        List of sessions with count
    """
    return await session_list()
