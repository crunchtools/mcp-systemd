"""Mocked tests for every tool the server registers."""

import asyncio
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from dbus_fast import MessageType

from mcp_systemd_crunchtools import dbus_client, server
from mcp_systemd_crunchtools.errors import (
    InvalidJournalPriorityError,
    InvalidUnitNameError,
    ProtectedUnitError,
    UnitFileValidationError,
    UnitNotFoundError,
)
from mcp_systemd_crunchtools.models import MAX_UNIT_FILE_BYTES, MAX_UNIT_NAME_LENGTH

from .conftest import FakeBus, FakeReply, default_handler

EXPECTED_TOOL_COUNT = 21

UNIT_CONTENT = """[Unit]
Description=Test App

[Service]
ExecStart=/usr/bin/true

[Install]
WantedBy=multi-user.target
"""


@pytest.mark.asyncio
async def test_tool_count() -> None:
    """Every registered tool is accounted for — update this when adding tools."""
    tools = await server.mcp.list_tools()
    assert len(tools) == EXPECTED_TOOL_COUNT


def test_module_is_executable() -> None:
    """`python -m mcp_systemd_crunchtools` must work — it is the container ENTRYPOINT.

    Importing the package is not enough: a missing __main__.py imports fine and
    then fails only at container start.
    """
    result = subprocess.run(
        [sys.executable, "-m", "mcp_systemd_crunchtools", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--transport" in result.stdout


@pytest.mark.asyncio
async def test_all_tools_have_descriptions() -> None:
    tools = await server.mcp.list_tools()
    for tool in tools:
        assert tool.description, f"{tool.name} has no description"


READ_ONLY = frozenset(
    {
        "unit_list_tool",
        "unit_status_tool",
        "unit_show_tool",
        "journal_query_tool",
        "failed_units_tool",
        "list_jobs_tool",
        "timer_list_tool",
        "system_status_tool",
        "hostinfo_tool",
        "session_list_tool",
    }
)
WRITES = frozenset(
    {
        "unit_start_tool",
        "unit_stop_tool",
        "unit_restart_tool",
        "unit_reload_tool",
        "unit_enable_tool",
        "unit_disable_tool",
        "unit_mask_tool",
        "unit_unmask_tool",
        "daemon_reload_tool",
        "unit_file_write_tool",
        "unit_file_remove_tool",
    }
)

# The D-Bus methods a read-only tool may call: each returns state and changes
# none. LoadUnit is the one that needs a reason. It resolves a unit name to its
# object path, as `systemctl status` and `systemctl show` do; systemd keeps the
# unit in memory only while something references it, and it queues no job,
# starts nothing and writes no file.
READ_DBUS_METHODS = frozenset(
    {
        (dbus_client.PROPS_IFACE, "Get"),
        (dbus_client.PROPS_IFACE, "GetAll"),
        (dbus_client.MANAGER_IFACE, "ListUnits"),
        (dbus_client.MANAGER_IFACE, "ListUnitFiles"),
        (dbus_client.MANAGER_IFACE, "ListJobs"),
        (dbus_client.MANAGER_IFACE, "LoadUnit"),
        (dbus_client.LOGIN_MANAGER_IFACE, "ListSessions"),
    }
)

# The journalctl options a read-only tool may pass, and whether each consumes
# the next argv element as its value. All of them select or format entries.
# --rotate, --vacuum-*, --flush, --sync and --relinquish-var are absent.
READ_JOURNALCTL_OPTIONS = {
    "--no-pager": False,
    "-n": True,
    "-u": True,
    "-p": True,
    "--since": True,
    "--until": True,
    "-g": True,
    "-b": True,
}

# One or more calls per read-only tool, covering every branch that picks a
# different backend call.
READ_ONLY_CALLS: list[tuple[str, dict[str, Any]]] = [
    ("unit_list_tool", {}),
    ("unit_list_tool", {"all_units": True, "pattern": "*.timer", "mode": "files"}),
    ("unit_status_tool", {"unit_name": "myapp.service"}),
    ("unit_status_tool", {"unit_name": "backup.timer"}),
    ("unit_show_tool", {"unit_name": "myapp.service"}),
    ("unit_show_tool", {"unit_name": "multi-user.target"}),
    ("journal_query_tool", {}),
    (
        "journal_query_tool",
        {
            "unit": "myapp.service",
            "priority": "err",
            "since": "1 hour ago",
            "until": "now",
            "pattern": "boom",
            "boot": -1,
            "lines": 50,
        },
    ),
    ("failed_units_tool", {}),
    ("list_jobs_tool", {}),
    ("timer_list_tool", {}),
    ("system_status_tool", {}),
    ("hostinfo_tool", {}),
    ("session_list_tool", {}),
]

WRITE_CALLS: dict[str, dict[str, Any]] = {
    "unit_start_tool": {"unit_name": "myapp.service"},
    "unit_stop_tool": {"unit_name": "myapp.service"},
    "unit_restart_tool": {"unit_name": "myapp.service"},
    "unit_reload_tool": {"unit_name": "myapp.service"},
    "unit_enable_tool": {"unit_name": "myapp.service"},
    "unit_disable_tool": {"unit_name": "myapp.service"},
    "unit_mask_tool": {"unit_name": "myapp.service"},
    "unit_unmask_tool": {"unit_name": "myapp.service"},
    "daemon_reload_tool": {},
    "unit_file_write_tool": {"unit_name": "myapp.service", "content": UNIT_CONTENT},
    "unit_file_remove_tool": {"unit_name": "myapp.service"},
}


class BackendRecorder:
    """Records every way a tool can reach the host: D-Bus, a subprocess, the unit dir."""

    def __init__(self, bus: FakeBus) -> None:
        self.bus = bus
        self.argvs: list[list[str]] = []
        self.disk_writes: list[str] = []

    def backend_calls(self) -> int:
        return len(self.bus.calls) + len(self.argvs)

    def state_changes(self) -> list[str]:
        """Everything recorded that is not on the read allowlists."""
        changes = [
            f"dbus {msg.interface}.{msg.member}"
            for msg in self.bus.calls
            if (msg.interface, msg.member) not in READ_DBUS_METHODS
        ]
        for argv in self.argvs:
            changes += _journalctl_state_changes(argv)
        return changes + self.disk_writes


def _journalctl_state_changes(argv: list[str]) -> list[str]:
    """Options in a subprocess argv that are not read options of journalctl."""
    if argv[0] != "journalctl":
        return [f"exec {argv[0]}"]
    changes = []
    rest = argv[1:]
    while rest:
        option = rest.pop(0)
        if option not in READ_JOURNALCTL_OPTIONS:
            changes.append(f"journalctl {option}")
        elif READ_JOURNALCTL_OPTIONS[option] and rest:
            rest.pop(0)
    return changes


@pytest.fixture
def backend(monkeypatch: pytest.MonkeyPatch, fake_bus: FakeBus) -> BackendRecorder:
    """Fake the bus and journalctl, and record writes to disk before letting them through."""
    recorder = BackendRecorder(fake_bus)

    class FakeProc:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"Sep 19 02:00:00 lotor myapp[1]: boom\n", b""

    async def fake_exec(*args: str, **kwargs: Any) -> FakeProc:
        recorder.argvs.append(list(args))
        return FakeProc()

    def recording(label: str, original: Any) -> Any:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            recorder.disk_writes.append(f"disk {label}")
            return original(*args, **kwargs)

        return wrapper

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(Path, "write_text", recording("write_text", Path.write_text))
    monkeypatch.setattr(Path, "unlink", recording("unlink", Path.unlink))
    monkeypatch.setattr(shutil, "copy2", recording("copy2", shutil.copy2))
    return recorder


class TestReadOnlyAnnotation:
    """Every registered tool is classified, and the reads really only read."""

    @pytest.mark.asyncio
    async def test_every_tool_is_classified(self) -> None:
        tools = await server.mcp.list_tools()
        assert READ_ONLY.isdisjoint(WRITES)
        assert {tool.name for tool in tools} == READ_ONLY | WRITES
        annotated = {
            tool.name
            for tool in tools
            if tool.annotations is not None
            and tool.annotations.model_dump(by_alias=True).get("readOnlyHint") is True
        }
        assert annotated == READ_ONLY

    def test_call_tables_cover_both_sets(self) -> None:
        assert {name for name, _ in READ_ONLY_CALLS} == READ_ONLY
        assert set(WRITE_CALLS) == WRITES

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("name", "arguments"), READ_ONLY_CALLS)
    async def test_read_only_tool_changes_nothing(
        self, backend: BackendRecorder, name: str, arguments: dict[str, Any]
    ) -> None:
        await server.mcp.call_tool(name, arguments)
        assert backend.backend_calls() >= 1
        assert backend.state_changes() == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("name", sorted(WRITES))
    async def test_every_write_tool_trips_the_same_check(
        self, backend: BackendRecorder, name: str
    ) -> None:
        """Control: the check above fails for each tool that is not annotated."""
        await server.mcp.call_tool(name, WRITE_CALLS[name])
        assert backend.state_changes() != []

    def test_a_journalctl_write_option_is_caught(self) -> None:
        """Control for the argv check: --rotate is flagged, a value that looks like it is not."""
        assert _journalctl_state_changes(["journalctl", "--no-pager", "--rotate"]) == [
            "journalctl --rotate"
        ]
        assert _journalctl_state_changes(["journalctl", "--since", "--rotate"]) == []
        assert _journalctl_state_changes(["systemctl", "restart", "sshd.service"]) == [
            "exec systemctl"
        ]


class TestJsonable:
    def test_a_byte_array_is_hex_as_systemctl_prints_it(self) -> None:
        raw = bytes.fromhex("e51a77aca16647f18451d0626d66789c")
        assert dbus_client._to_jsonable(raw) == "e51a77aca16647f18451d0626d66789c"
        assert dbus_client._to_jsonable(bytearray(raw)) == raw.hex()

    def test_a_byte_array_inside_a_variant_or_a_list_is_hex(self) -> None:
        raw = b"\xe5\x1a"
        assert dbus_client._to_jsonable(dbus_client.Variant("ay", raw)) == "e51a"
        assert dbus_client._to_jsonable({"ids": [raw]}) == {"ids": ["e51a"]}


class TestUnitQueries:
    @pytest.mark.asyncio
    async def test_unit_list_skips_inactive_by_default(self, fake_bus: FakeBus) -> None:
        result = await dbus_client.unit_list()
        names = [item["unit"] for item in result["items"]]
        assert "myapp.service" in names
        assert "dead.service" not in names
        assert result["count"] == len(result["items"])

    @pytest.mark.asyncio
    async def test_unit_list_all_includes_inactive(self, fake_bus: FakeBus) -> None:
        result = await dbus_client.unit_list(all_units=True)
        assert "dead.service" in [item["unit"] for item in result["items"]]

    @pytest.mark.asyncio
    async def test_unit_list_filters_by_pattern(self, fake_bus: FakeBus) -> None:
        result = await dbus_client.unit_list(all_units=True, pattern="*.timer")
        assert [item["unit"] for item in result["items"]] == ["backup.timer"]

    @pytest.mark.asyncio
    async def test_unit_list_files_mode(self, fake_bus: FakeBus) -> None:
        result = await dbus_client.unit_list(mode="files")
        assert "ListUnitFiles" in fake_bus.members()
        assert result["items"][0]["state"] == "enabled"

    @pytest.mark.asyncio
    async def test_unit_status_includes_service_properties(self, fake_bus: FakeBus) -> None:
        result = await dbus_client.unit_status("myapp.service")
        assert result["properties"]["ActiveState"] == "active"
        assert result["properties"]["MainPID"] == 4242

    @pytest.mark.asyncio
    async def test_unit_status_rejects_a_path(self, fake_bus: FakeBus) -> None:
        with pytest.raises(InvalidUnitNameError):
            await dbus_client.unit_status("../../etc/passwd")

    @pytest.mark.asyncio
    async def test_unit_status_raises_when_not_found(
        self, monkeypatch: pytest.MonkeyPatch, fake_bus: FakeBus
    ) -> None:
        def handler(msg: Any) -> FakeReply:
            if msg.member == "Get" and msg.body[1] == "LoadState":
                return FakeReply(["not-found"])
            return default_handler(msg)

        fake_bus.handler = handler
        with pytest.raises(UnitNotFoundError):
            await dbus_client.unit_status("ghost.service")

    @pytest.mark.asyncio
    async def test_unit_show_merges_type_interface(self, fake_bus: FakeBus) -> None:
        result = await dbus_client.unit_show("myapp.service")
        assert result["properties"]["Description"] == "My App"
        assert result["properties"]["Result"] == "success"

    @pytest.mark.asyncio
    async def test_unit_show_on_a_target_has_no_type_properties(self, fake_bus: FakeBus) -> None:
        result = await dbus_client.unit_show("multi-user.target")
        assert "Result" not in result["properties"]


class TestLifecycle:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("func", "member", "status"),
        [
            (dbus_client.unit_start, "StartUnit", "started"),
            (dbus_client.unit_stop, "StopUnit", "stopped"),
            (dbus_client.unit_restart, "RestartUnit", "restarted"),
            (dbus_client.unit_reload, "ReloadUnit", "reloaded"),
        ],
    )
    async def test_transitions(
        self, fake_bus: FakeBus, func: Any, member: str, status: str
    ) -> None:
        result = await func("myapp.service")
        assert result == {"status": status, "unit": "myapp.service"}
        assert member in fake_bus.members()
        assert fake_bus.disconnected

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("func", "member", "status"),
        [
            (dbus_client.unit_enable, "EnableUnitFiles", "enabled"),
            (dbus_client.unit_disable, "DisableUnitFiles", "disabled"),
            (dbus_client.unit_mask, "MaskUnitFiles", "masked"),
            (dbus_client.unit_unmask, "UnmaskUnitFiles", "unmasked"),
        ],
    )
    async def test_unit_file_state_changes_reload_afterwards(
        self, fake_bus: FakeBus, func: Any, member: str, status: str
    ) -> None:
        result = await func("myapp.service")
        assert result["status"] == status
        assert result["changes"][0]["type"] == "symlink"
        assert fake_bus.members() == [member, "Reload"]

    @pytest.mark.asyncio
    async def test_daemon_reload(self, fake_bus: FakeBus) -> None:
        assert await dbus_client.daemon_reload() == {"status": "reloaded"}
        assert fake_bus.members() == ["Reload"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("func", "action"),
        [
            (dbus_client.unit_stop, "stop"),
            (dbus_client.unit_restart, "restart"),
            (dbus_client.unit_disable, "disable"),
            (dbus_client.unit_mask, "mask"),
        ],
    )
    async def test_protected_units_are_refused(
        self, fake_bus: FakeBus, func: Any, action: str
    ) -> None:
        with pytest.raises(ProtectedUnitError, match=action):
            await func("sshd.service")
        assert fake_bus.calls == []

    @pytest.mark.asyncio
    async def test_starting_a_protected_unit_is_allowed(self, fake_bus: FakeBus) -> None:
        """Starting is never destructive — only stop/restart/disable/mask are gated."""
        assert (await dbus_client.unit_start("sshd.service"))["status"] == "started"


class TestUnitFiles:
    @pytest.mark.asyncio
    async def test_write_creates_the_file_and_reloads(self, fake_bus: FakeBus) -> None:
        result = await dbus_client.unit_file_write("myapp.service", UNIT_CONTENT)
        assert result["backup_path"] is None
        assert Path(result["path"]).read_text() == UNIT_CONTENT
        assert fake_bus.members() == ["Reload"]

    @pytest.mark.asyncio
    async def test_write_backs_up_an_existing_file(self, fake_bus: FakeBus) -> None:
        await dbus_client.unit_file_write("myapp.service", "old")
        result = await dbus_client.unit_file_write("myapp.service", UNIT_CONTENT)
        backup = result["backup_path"]
        assert backup is not None
        assert Path(backup).read_text() == "old"
        assert Path(result["path"]).read_text() == UNIT_CONTENT

    @pytest.mark.asyncio
    async def test_write_can_enable_and_start(self, fake_bus: FakeBus) -> None:
        result = await dbus_client.unit_file_write(
            "myapp.service", UNIT_CONTENT, enable=True, start=True
        )
        assert result["enable"]["status"] == "enabled"
        assert result["start"]["status"] == "started"

    @pytest.mark.asyncio
    async def test_write_rejects_traversal(self, fake_bus: FakeBus) -> None:
        with pytest.raises(InvalidUnitNameError):
            await dbus_client.unit_file_write("../evil.service", UNIT_CONTENT)

    @pytest.mark.asyncio
    async def test_remove_stops_disables_and_backs_up(self, fake_bus: FakeBus) -> None:
        written = await dbus_client.unit_file_write("myapp.service", UNIT_CONTENT)
        result = await dbus_client.unit_file_remove("myapp.service")
        assert result["removed"] is True
        assert result["steps"]["stop"]["status"] == "stopped"
        assert result["steps"]["disable"]["status"] == "disabled"
        assert not Path(written["path"]).exists()
        assert Path(result["backup_path"]).read_text() == UNIT_CONTENT

    @pytest.mark.asyncio
    async def test_remove_survives_a_unit_that_was_never_started(self, fake_bus: FakeBus) -> None:
        await dbus_client.unit_file_write("myapp.service", UNIT_CONTENT)

        def handler(msg: Any) -> FakeReply:
            if msg.member == "StopUnit":
                return FakeReply(["not loaded"], MessageType.ERROR)
            return default_handler(msg)

        fake_bus.handler = handler
        result = await dbus_client.unit_file_remove("myapp.service")
        assert result["steps"]["stop"]["status"] == "skipped"
        assert result["removed"] is True

    @pytest.mark.asyncio
    async def test_remove_can_mask(self, fake_bus: FakeBus) -> None:
        await dbus_client.unit_file_write("myapp.service", UNIT_CONTENT)
        result = await dbus_client.unit_file_remove("myapp.service", mask=True)
        assert result["steps"]["mask"]["status"] == "masked"

    @pytest.mark.asyncio
    async def test_remove_refuses_protected_units(self, fake_bus: FakeBus) -> None:
        with pytest.raises(ProtectedUnitError, match="remove"):
            await dbus_client.unit_file_remove("sshd.service")

    @pytest.mark.asyncio
    async def test_remove_of_a_missing_file_reports_not_removed(self, fake_bus: FakeBus) -> None:
        result = await dbus_client.unit_file_remove("ghost.service")
        assert result["removed"] is False
        assert result["backup_path"] is None


class TestUnitFileWriteToolValidation:
    """RT #1492 — unit_file_write_tool enforces UnitFileWriteInput, not just the unit name."""

    @pytest.mark.asyncio
    async def test_valid_input_still_writes_and_reloads(self, fake_bus: FakeBus) -> None:
        result = await server.unit_file_write_tool("myapp.service", UNIT_CONTENT)
        assert result["backup_path"] is None
        assert Path(result["path"]).read_text() == UNIT_CONTENT
        assert fake_bus.members() == ["Reload"]

    @pytest.mark.asyncio
    async def test_valid_input_can_enable_and_start(self, fake_bus: FakeBus) -> None:
        result = await server.unit_file_write_tool(
            "myapp.service", UNIT_CONTENT, enable=True, start=True
        )
        assert result["enable"]["status"] == "enabled"
        assert result["start"]["status"] == "started"

    @pytest.mark.asyncio
    async def test_rejects_empty_content(self, fake_bus: FakeBus) -> None:
        with pytest.raises(UnitFileValidationError):
            await server.unit_file_write_tool("myapp.service", "")
        assert fake_bus.members() == []

    @pytest.mark.asyncio
    async def test_rejects_oversized_content(self, fake_bus: FakeBus) -> None:
        with pytest.raises(UnitFileValidationError):
            await server.unit_file_write_tool("myapp.service", "x" * (MAX_UNIT_FILE_BYTES + 1))
        assert fake_bus.members() == []

    @pytest.mark.asyncio
    async def test_rejects_oversized_unit_name(self, fake_bus: FakeBus) -> None:
        with pytest.raises(UnitFileValidationError):
            await server.unit_file_write_tool(
                "a" * (MAX_UNIT_NAME_LENGTH + 1) + ".service", UNIT_CONTENT
            )
        assert fake_bus.members() == []

    @pytest.mark.asyncio
    async def test_no_disk_write_on_rejected_input(self, fake_bus: FakeBus, tmp_path: Path) -> None:
        with pytest.raises(UnitFileValidationError):
            await server.unit_file_write_tool("myapp.service", "")
        assert list(tmp_path.rglob("myapp.service")) == []


class TestTroubleshooting:
    @pytest.mark.asyncio
    async def test_failed_units(self, fake_bus: FakeBus) -> None:
        result = await dbus_client.failed_units()
        assert result["count"] == 1
        assert result["items"][0]["unit"] == "broken.service"

    @pytest.mark.asyncio
    async def test_list_jobs(self, fake_bus: FakeBus) -> None:
        result = await dbus_client.list_jobs()
        assert result["items"][0] == {
            "id": 42,
            "unit": "myapp.service",
            "job_type": "start",
            "state": "running",
        }

    @pytest.mark.asyncio
    async def test_journal_query_builds_argv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[str] = []

        class FakeProc:
            returncode = 0

            async def communicate(self) -> tuple[bytes, bytes]:
                return b"Sep 19 02:00:00 lotor myapp[1]: boom\n", b""

        async def fake_exec(*args: str, **kwargs: Any) -> FakeProc:
            captured.extend(args)
            return FakeProc()

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        result = await dbus_client.journal_query(
            unit="myapp.service",
            priority="err",
            since="1 hour ago",
            until="now",
            pattern="boom",
            boot=0,
            lines=50,
        )
        assert "boom" in result["logs"]
        assert captured[:4] == ["journalctl", "--no-pager", "-n", "50"]
        for flag, value in (
            ("-u", "myapp.service"),
            ("-p", "err"),
            ("--since", "1 hour ago"),
            ("--until", "now"),
            ("-g", "boom"),
            ("-b", "0"),
        ):
            assert captured[captured.index(flag) + 1] == value

    @pytest.mark.asyncio
    async def test_journal_query_rejects_a_bad_priority(self) -> None:
        with pytest.raises(InvalidJournalPriorityError):
            await dbus_client.journal_query(priority="--output=cat")

    @pytest.mark.asyncio
    async def test_journal_query_rejects_a_bad_unit(self) -> None:
        with pytest.raises(InvalidUnitNameError):
            await dbus_client.journal_query(unit="/etc/shadow")


class TestSystemAndSessions:
    @pytest.mark.asyncio
    async def test_timer_list(self, fake_bus: FakeBus) -> None:
        result = await dbus_client.timer_list()
        assert result["count"] == 1
        timer = result["items"][0]
        assert timer["unit"] == "backup.timer"
        assert timer["next_elapse"].startswith("2025-")

    @pytest.mark.asyncio
    async def test_system_status(self, fake_bus: FakeBus) -> None:
        result = await dbus_client.system_status()
        assert result["SystemState"] == "running"
        assert result["NFailedUnits"] == 1

    @pytest.mark.asyncio
    async def test_hostinfo(self, fake_bus: FakeBus) -> None:
        result = await dbus_client.hostinfo()
        assert result["Hostname"] == "lotor"
        assert result["KernelName"] == "Linux"

    @pytest.mark.asyncio
    async def test_session_list(self, fake_bus: FakeBus) -> None:
        result = await dbus_client.session_list()
        assert result["items"][0]["user"] == "fatherlinux"
        assert result["items"][0]["state"] == "active"
