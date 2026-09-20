"""Async D-Bus client for systemd, hostname1, and login1.

Talks directly to the system D-Bus API over the system bus socket — no
systemctl/hostnamectl/loginctl subprocess calls, except journalctl, which
has no D-Bus equivalent for arbitrary filtered queries.

Uses dbus-fast for async D-Bus communication — this works inside
containers without requiring PID 1 to be systemd.
"""

import asyncio
import fnmatch
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dbus_fast import Message, MessageType, Variant
from dbus_fast.aio import MessageBus

from .config import get_config, validate_dbus_socket
from .errors import (
    InvalidJournalPriorityError,
    InvalidUnitNameError,
    ProtectedUnitError,
    UnitFileError,
    UnitNotFoundError,
    UnitOperationError,
)
from .models import ALLOWED_JOURNAL_PRIORITIES, UNIT_NAME_PATTERN

logger = logging.getLogger(__name__)

SYSTEMD_BUS = "org.freedesktop.systemd1"
SYSTEMD_PATH = "/org/freedesktop/systemd1"
MANAGER_IFACE = "org.freedesktop.systemd1.Manager"
UNIT_IFACE = "org.freedesktop.systemd1.Unit"
SERVICE_IFACE = "org.freedesktop.systemd1.Service"
TIMER_IFACE = "org.freedesktop.systemd1.Timer"
PROPS_IFACE = "org.freedesktop.DBus.Properties"

HOSTNAME_BUS = "org.freedesktop.hostname1"
HOSTNAME_PATH = "/org/freedesktop/hostname1"
HOSTNAME_IFACE = "org.freedesktop.hostname1"

LOGIN_BUS = "org.freedesktop.login1"
LOGIN_PATH = "/org/freedesktop/login1"
LOGIN_MANAGER_IFACE = "org.freedesktop.login1.Manager"
LOGIN_SESSION_IFACE = "org.freedesktop.login1.Session"

MICROSECONDS_PER_SECOND = 1_000_000


def validate_unit_name(name: str) -> str:
    """Validate a bare unit name (no paths, no traversal). Returns it unchanged."""
    if not UNIT_NAME_PATTERN.match(name):
        raise InvalidUnitNameError(name)
    return name


def assert_not_protected(name: str, action: str) -> None:
    """Raise ProtectedUnitError if name is on the protected-unit denylist."""
    if name in get_config().protected_units:
        raise ProtectedUnitError(name, action)


def _to_jsonable(value: Any) -> Any:
    """Recursively unwrap Variants and coerce to JSON-safe primitives."""
    if isinstance(value, Variant):
        value = value.value
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list | tuple):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    return str(value)


async def _get_bus() -> MessageBus:
    """Connect to the system D-Bus."""
    socket_path = get_config().dbus_socket
    validate_dbus_socket(socket_path)
    return await MessageBus(bus_address=f"unix:path={socket_path}").connect()


async def _call(
    bus: MessageBus, interface: str, member: str,
    signature: str = "", body: list[Any] | None = None,
    path: str = SYSTEMD_PATH, destination: str = SYSTEMD_BUS,
) -> Message:
    """Make a D-Bus method call."""
    msg = Message(
        destination=destination,
        path=path,
        interface=interface,
        member=member,
        signature=signature,
        body=body or [],
    )
    reply = await bus.call(msg)
    if reply.message_type == MessageType.ERROR:
        raise UnitOperationError(f"{interface}.{member} failed: {reply.body}")
    return reply


async def _get_property(
    bus: MessageBus, path: str, iface: str, prop: str, destination: str = SYSTEMD_BUS,
) -> Any:
    """Get a single property from a D-Bus object. Returns None on any failure."""
    msg = Message(
        destination=destination, path=path, interface=PROPS_IFACE,
        member="Get", signature="ss", body=[iface, prop],
    )
    reply = await bus.call(msg)
    if reply.message_type == MessageType.ERROR:
        return None
    return _to_jsonable(reply.body[0])


async def _get_all_properties(
    bus: MessageBus, path: str, iface: str, destination: str = SYSTEMD_BUS,
) -> dict[str, Any]:
    """Get all properties for an interface. Returns {} on failure."""
    msg = Message(
        destination=destination, path=path, interface=PROPS_IFACE,
        member="GetAll", signature="s", body=[iface],
    )
    reply = await bus.call(msg)
    if reply.message_type == MessageType.ERROR:
        return {}
    return {k: _to_jsonable(v) for k, v in reply.body[0].items()}


async def _get_unit_path(bus: MessageBus, unit_name: str) -> str:
    """Get the D-Bus object path for a systemd unit, loading it if needed."""
    reply = await _call(bus, MANAGER_IFACE, "LoadUnit", "s", [unit_name])
    return str(reply.body[0])


async def _require_loaded_unit(bus: MessageBus, unit_name: str) -> str:
    """Get a unit's path and confirm it actually exists (LoadState != not-found)."""
    unit_path = await _get_unit_path(bus, unit_name)
    load_state = await _get_property(bus, unit_path, UNIT_IFACE, "LoadState")
    if load_state == "not-found":
        raise UnitNotFoundError(unit_name)
    return unit_path


def _unit_type_iface(unit_name: str) -> str | None:
    """Map a unit suffix to its type-specific D-Bus interface, if any."""
    suffix_iface = {
        ".service": SERVICE_IFACE,
        ".timer": TIMER_IFACE,
    }
    for suffix, iface in suffix_iface.items():
        if unit_name.endswith(suffix):
            return iface
    return None


async def unit_list(
    all_units: bool = False, pattern: str | None = None, mode: str = "loaded",
) -> dict[str, Any]:
    """List systemd units (loaded, in memory) or installed unit files."""
    bus = await _get_bus()
    try:
        if mode == "files":
            reply = await _call(bus, MANAGER_IFACE, "ListUnitFiles")
            items = [
                {"path": path, "state": state}
                for path, state in reply.body[0]
                if pattern is None or fnmatch.fnmatch(path.rsplit("/", 1)[-1], pattern)
            ]
            return {"items": items, "count": len(items)}

        reply = await _call(bus, MANAGER_IFACE, "ListUnits")
        active_states = {"active", "activating", "failed", "reloading"}
        items = []
        for unit in reply.body[0]:
            name = unit[0]
            active_state = unit[3]
            if pattern is not None and not fnmatch.fnmatch(name, pattern):
                continue
            if not all_units and active_state not in active_states:
                continue
            items.append({
                "unit": name,
                "description": unit[1],
                "load": unit[2],
                "active": active_state,
                "sub": unit[4],
            })
        return {"items": items, "count": len(items)}
    finally:
        bus.disconnect()


async def unit_status(unit_name: str) -> dict[str, Any]:
    """Get curated status properties for a unit."""
    validate_unit_name(unit_name)
    bus = await _get_bus()
    try:
        unit_path = await _require_loaded_unit(bus, unit_name)
        props: dict[str, Any] = {}
        for prop in ("ActiveState", "SubState", "LoadState", "Description", "InvocationID"):
            props[prop] = await _get_property(bus, unit_path, UNIT_IFACE, prop) or "unknown"

        type_iface = _unit_type_iface(unit_name)
        if type_iface == SERVICE_IFACE:
            for prop in ("MainPID", "MemoryCurrent", "CPUUsageNSec", "Result", "ExecMainStatus"):
                value = await _get_property(bus, unit_path, SERVICE_IFACE, prop)
                props[prop] = value if value is not None else "unknown"

        return {"unit": unit_name, "properties": props}
    finally:
        bus.disconnect()


async def unit_show(unit_name: str) -> dict[str, Any]:
    """Dump the full property set for a unit (Unit iface + type-specific iface)."""
    validate_unit_name(unit_name)
    bus = await _get_bus()
    try:
        unit_path = await _require_loaded_unit(bus, unit_name)
        properties = await _get_all_properties(bus, unit_path, UNIT_IFACE)
        type_iface = _unit_type_iface(unit_name)
        if type_iface:
            properties.update(await _get_all_properties(bus, unit_path, type_iface))
        return {"unit": unit_name, "properties": properties}
    finally:
        bus.disconnect()


async def unit_start(unit_name: str) -> dict[str, Any]:
    """Start a unit."""
    validate_unit_name(unit_name)
    bus = await _get_bus()
    try:
        await _call(bus, MANAGER_IFACE, "StartUnit", "ss", [unit_name, "replace"])
        return {"status": "started", "unit": unit_name}
    finally:
        bus.disconnect()


async def unit_stop(unit_name: str) -> dict[str, Any]:
    """Stop a unit."""
    validate_unit_name(unit_name)
    assert_not_protected(unit_name, "stop")
    bus = await _get_bus()
    try:
        await _call(bus, MANAGER_IFACE, "StopUnit", "ss", [unit_name, "replace"])
        return {"status": "stopped", "unit": unit_name}
    finally:
        bus.disconnect()


async def unit_restart(unit_name: str) -> dict[str, Any]:
    """Restart a unit."""
    validate_unit_name(unit_name)
    assert_not_protected(unit_name, "restart")
    bus = await _get_bus()
    try:
        await _call(bus, MANAGER_IFACE, "RestartUnit", "ss", [unit_name, "replace"])
        return {"status": "restarted", "unit": unit_name}
    finally:
        bus.disconnect()


async def unit_reload(unit_name: str) -> dict[str, Any]:
    """Ask a unit to reload its configuration without restarting."""
    validate_unit_name(unit_name)
    bus = await _get_bus()
    try:
        await _call(bus, MANAGER_IFACE, "ReloadUnit", "ss", [unit_name, "replace"])
        return {"status": "reloaded", "unit": unit_name}
    finally:
        bus.disconnect()


async def unit_enable(unit_name: str) -> dict[str, Any]:
    """Enable a unit to start on boot, then reload the daemon's unit cache."""
    validate_unit_name(unit_name)
    bus = await _get_bus()
    try:
        reply = await _call(
            bus, MANAGER_IFACE, "EnableUnitFiles", "asbb", [[unit_name], False, False],
        )
        changes = [{"type": c[0], "path": c[1], "target": c[2]} for c in reply.body[1]]
        await _call(bus, MANAGER_IFACE, "Reload")
        return {"status": "enabled", "unit": unit_name, "changes": changes}
    finally:
        bus.disconnect()


async def unit_disable(unit_name: str) -> dict[str, Any]:
    """Disable a unit from starting on boot, then reload the daemon's unit cache."""
    validate_unit_name(unit_name)
    assert_not_protected(unit_name, "disable")
    bus = await _get_bus()
    try:
        reply = await _call(bus, MANAGER_IFACE, "DisableUnitFiles", "asb", [[unit_name], False])
        changes = [{"type": c[0], "path": c[1], "target": c[2]} for c in reply.body[0]]
        await _call(bus, MANAGER_IFACE, "Reload")
        return {"status": "disabled", "unit": unit_name, "changes": changes}
    finally:
        bus.disconnect()


async def unit_mask(unit_name: str) -> dict[str, Any]:
    """Mask a unit (symlink to /dev/null — cannot be started even manually)."""
    validate_unit_name(unit_name)
    assert_not_protected(unit_name, "mask")
    bus = await _get_bus()
    try:
        reply = await _call(
            bus, MANAGER_IFACE, "MaskUnitFiles", "asbb", [[unit_name], False, False],
        )
        changes = [{"type": c[0], "path": c[1], "target": c[2]} for c in reply.body[0]]
        await _call(bus, MANAGER_IFACE, "Reload")
        return {"status": "masked", "unit": unit_name, "changes": changes}
    finally:
        bus.disconnect()


async def unit_unmask(unit_name: str) -> dict[str, Any]:
    """Unmask a previously masked unit."""
    validate_unit_name(unit_name)
    bus = await _get_bus()
    try:
        reply = await _call(bus, MANAGER_IFACE, "UnmaskUnitFiles", "asb", [[unit_name], False])
        changes = [{"type": c[0], "path": c[1], "target": c[2]} for c in reply.body[0]]
        await _call(bus, MANAGER_IFACE, "Reload")
        return {"status": "unmasked", "unit": unit_name, "changes": changes}
    finally:
        bus.disconnect()


async def daemon_reload() -> dict[str, Any]:
    """Reload systemd's unit file cache (equivalent to systemctl daemon-reload)."""
    bus = await _get_bus()
    try:
        await _call(bus, MANAGER_IFACE, "Reload")
        return {"status": "reloaded"}
    finally:
        bus.disconnect()


async def failed_units() -> dict[str, Any]:
    """List units currently in the 'failed' state."""
    bus = await _get_bus()
    try:
        reply = await _call(bus, MANAGER_IFACE, "ListUnits")
        items = [
            {"unit": u[0], "description": u[1], "active": u[3], "sub": u[4]}
            for u in reply.body[0]
            if u[3] == "failed"
        ]
        return {"items": items, "count": len(items)}
    finally:
        bus.disconnect()


async def list_jobs() -> dict[str, Any]:
    """List pending systemd jobs (starts/stops/reloads in progress or queued)."""
    bus = await _get_bus()
    try:
        reply = await _call(bus, MANAGER_IFACE, "ListJobs")
        items = [
            {"id": j[0], "unit": j[1], "job_type": j[2], "state": j[3]}
            for j in reply.body[0]
        ]
        return {"items": items, "count": len(items)}
    finally:
        bus.disconnect()


def _usec_to_iso(usec: int) -> str | None:
    """Convert a systemd realtime microsecond timestamp to ISO 8601, or None if unset."""
    if not usec:
        return None
    return datetime.fromtimestamp(usec / MICROSECONDS_PER_SECOND, tz=timezone.utc).isoformat()


async def timer_list() -> dict[str, Any]:
    """List systemd timers with their next and last elapse times."""
    bus = await _get_bus()
    try:
        reply = await _call(bus, MANAGER_IFACE, "ListUnits")
        items = []
        for unit in reply.body[0]:
            name = unit[0]
            if not name.endswith(".timer"):
                continue
            unit_path = unit[6]
            next_elapse = await _get_property(bus, unit_path, TIMER_IFACE, "NextElapseUSecRealtime")
            last_trigger = await _get_property(bus, unit_path, TIMER_IFACE, "LastTriggerUSec")
            items.append({
                "unit": name,
                "active": unit[3],
                "next_elapse": _usec_to_iso(next_elapse or 0),
                "last_trigger": _usec_to_iso(last_trigger or 0),
            })
        return {"items": items, "count": len(items)}
    finally:
        bus.disconnect()


async def system_status() -> dict[str, Any]:
    """Get overall systemd manager state."""
    bus = await _get_bus()
    try:
        props: dict[str, Any] = {}
        for prop in ("SystemState", "Version", "NFailedUnits", "NJobs", "NNames"):
            props[prop] = await _get_property(bus, SYSTEMD_PATH, MANAGER_IFACE, prop)
        return props
    finally:
        bus.disconnect()


async def hostinfo() -> dict[str, Any]:
    """Get host identity info from org.freedesktop.hostname1."""
    bus = await _get_bus()
    try:
        props: dict[str, Any] = {}
        for prop in (
            "Hostname", "StaticHostname", "PrettyHostname", "Chassis",
            "KernelName", "KernelRelease", "OperatingSystemPrettyName",
        ):
            value = await _get_property(
                bus, HOSTNAME_PATH, HOSTNAME_IFACE, prop, destination=HOSTNAME_BUS,
            )
            props[prop] = value if value is not None else "unknown"
        return props
    finally:
        bus.disconnect()


async def session_list() -> dict[str, Any]:
    """List logged-in sessions from org.freedesktop.login1."""
    bus = await _get_bus()
    try:
        reply = await _call(
            bus, LOGIN_MANAGER_IFACE, "ListSessions",
            path=LOGIN_PATH, destination=LOGIN_BUS,
        )
        items = []
        for session_id, uid, user_name, seat_id, session_path in reply.body[0]:
            state = await _get_property(
                bus, session_path, LOGIN_SESSION_IFACE, "State", destination=LOGIN_BUS,
            )
            tty = await _get_property(
                bus, session_path, LOGIN_SESSION_IFACE, "TTY", destination=LOGIN_BUS,
            )
            items.append({
                "session_id": session_id,
                "uid": uid,
                "user": user_name,
                "seat": seat_id or "n/a",
                "state": state or "unknown",
                "tty": tty or "n/a",
            })
        return {"items": items, "count": len(items)}
    finally:
        bus.disconnect()


def _resolve_unit_path(unit_name: str) -> Path:
    """Resolve unit_name to a path inside the configured unit dir, rejecting escapes."""
    unit_dir = Path(get_config().unit_dir).resolve()
    target = (unit_dir / unit_name).resolve()
    if target.parent != unit_dir:
        raise InvalidUnitNameError(unit_name)
    return target


async def unit_file_write(
    unit_name: str, content: str, enable: bool = False, start: bool = False,
) -> dict[str, Any]:
    """Write a unit file to the configured unit directory, backing up any existing file.

    Requires the host's unit directory (default /etc/systemd/system) to be
    bind-mounted into the container.
    """
    validate_unit_name(unit_name)
    target = _resolve_unit_path(unit_name)
    target.parent.mkdir(parents=True, exist_ok=True)

    backup_path = None
    if target.exists():
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = target.with_name(f"{unit_name}.bak-{timestamp}")
        shutil.copy2(target, backup_path)

    target.write_text(content)
    await daemon_reload()

    result: dict[str, Any] = {
        "unit": unit_name,
        "path": str(target),
        "backup_path": str(backup_path) if backup_path else None,
    }
    if enable:
        result["enable"] = await unit_enable(unit_name)
    if start:
        result["start"] = await unit_start(unit_name)
    return result


async def unit_file_remove(unit_name: str, mask: bool = False) -> dict[str, Any]:
    """Decommission a unit: stop, disable, optionally mask, back up and remove its file.

    Best-effort on stop/disable — a unit that is already stopped or was never
    enabled does not block removal of the file.
    """
    validate_unit_name(unit_name)
    assert_not_protected(unit_name, "remove")

    steps: dict[str, Any] = {}
    try:
        steps["stop"] = await unit_stop(unit_name)
    except UnitOperationError as exc:
        steps["stop"] = {"status": "skipped", "reason": str(exc)}

    try:
        steps["disable"] = await unit_disable(unit_name)
    except UnitOperationError as exc:
        steps["disable"] = {"status": "skipped", "reason": str(exc)}

    if mask:
        steps["mask"] = await unit_mask(unit_name)

    target = _resolve_unit_path(unit_name)
    backup_path = None
    if target.exists():
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = target.with_name(f"{unit_name}.bak-{timestamp}")
        shutil.copy2(target, backup_path)
        target.unlink()
        await daemon_reload()

    return {
        "unit": unit_name,
        "removed": backup_path is not None,
        "backup_path": str(backup_path) if backup_path else None,
        "steps": steps,
    }


async def journal_query(
    unit: str | None = None,
    priority: str | None = None,
    since: str | None = None,
    until: str | None = None,
    pattern: str | None = None,
    boot: int | None = None,
    lines: int = 100,
) -> dict[str, Any]:
    """Query the journal via journalctl (no D-Bus equivalent for filtered queries)."""
    if unit is not None:
        validate_unit_name(unit)
    if priority is not None and priority not in ALLOWED_JOURNAL_PRIORITIES:
        raise InvalidJournalPriorityError(priority)

    args = ["journalctl", "--no-pager", "-n", str(lines)]
    if unit:
        args += ["-u", unit]
    if priority:
        args += ["-p", priority]
    if since:
        args += ["--since", since]
    if until:
        args += ["--until", until]
    if pattern:
        args += ["-g", pattern]
    if boot is not None:
        args += ["-b", str(boot)]

    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode not in (0, None) and not stdout:
        raise UnitFileError(f"journalctl failed: {stderr.decode()}")
    return {"logs": stdout.decode(errors="replace")}
