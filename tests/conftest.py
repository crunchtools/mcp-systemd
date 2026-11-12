"""Shared fixtures.

Every test runs against a fake D-Bus bus — no system bus socket, no systemd,
no privileges. `fake_bus` replaces `dbus_client._get_bus`, so the wire logic
under test is exercised in full while the transport is canned.
"""

from typing import Any

import pytest
from dbus_fast import MessageType

from mcp_systemd_crunchtools import config as config_module
from mcp_systemd_crunchtools import dbus_client

UNIT_PATH = "/org/freedesktop/systemd1/unit/myapp_2eservice"

# (name, description, load, active, sub, followed, object_path, ...)
SAMPLE_UNITS = [
    ("myapp.service", "My App", "loaded", "active", "running", "", UNIT_PATH),
    ("broken.service", "Broken App", "loaded", "failed", "failed", "", UNIT_PATH),
    ("dead.service", "Dead App", "loaded", "inactive", "dead", "", UNIT_PATH),
    ("backup.timer", "Nightly Backup", "loaded", "active", "waiting", "", UNIT_PATH),
]

SAMPLE_UNIT_FILES = [
    ("/etc/systemd/system/myapp.service", "enabled"),
    ("/usr/lib/systemd/system/sshd.service", "enabled"),
]

SAMPLE_JOBS = [(42, "myapp.service", "start", "running", "/job/42", UNIT_PATH)]

SAMPLE_SESSIONS = [("3", 1000, "fatherlinux", "seat0", "/org/freedesktop/login1/session/_33")]

SAMPLE_CHANGES = [("symlink", "/etc/systemd/system/multi-user.target.wants/myapp.service", "")]

UNIT_PROPERTIES = {
    "ActiveState": "active",
    "SubState": "running",
    "LoadState": "loaded",
    "Description": "My App",
    "InvocationID": "abc123",
}

SERVICE_PROPERTIES = {
    "MainPID": 4242,
    "MemoryCurrent": 1048576,
    "CPUUsageNSec": 90000000,
    "Result": "success",
    "ExecMainStatus": 0,
}

MANAGER_PROPERTIES = {
    "SystemState": "running",
    "Version": "257",
    "NFailedUnits": 1,
    "NJobs": 0,
    "NNames": 380,
}

HOSTNAME_PROPERTIES = {
    "Hostname": "lotor",
    "StaticHostname": "lotor",
    "PrettyHostname": "lotor",
    "Chassis": "server",
    "KernelName": "Linux",
    "KernelRelease": "6.12.0",
    "OperatingSystemPrettyName": "Red Hat Enterprise Linux 10.0",
}

SESSION_PROPERTIES = {"State": "active", "TTY": "pts/0"}

TIMER_PROPERTIES = {
    "NextElapseUSecRealtime": 1_758_000_000_000_000,
    "LastTriggerUSec": 1_757_900_000_000_000,
}


class FakeReply:
    """Stands in for a dbus_fast Message reply."""

    def __init__(self, body: list[Any], message_type: MessageType = MessageType.METHOD_RETURN):
        self.body = body
        self.message_type = message_type


PROPERTY_TABLES = {
    dbus_client.UNIT_IFACE: UNIT_PROPERTIES,
    dbus_client.SERVICE_IFACE: SERVICE_PROPERTIES,
    dbus_client.TIMER_IFACE: TIMER_PROPERTIES,
    dbus_client.MANAGER_IFACE: MANAGER_PROPERTIES,
    dbus_client.HOSTNAME_IFACE: HOSTNAME_PROPERTIES,
    dbus_client.LOGIN_SESSION_IFACE: SESSION_PROPERTIES,
}


def default_handler(msg: Any) -> FakeReply:
    """Canned replies for every D-Bus method this server calls."""
    if msg.interface == dbus_client.PROPS_IFACE:
        table = PROPERTY_TABLES.get(msg.body[0], {})
        if msg.member == "GetAll":
            return FakeReply([dict(table)])
        value = table.get(msg.body[1])
        if value is None:
            return FakeReply([], MessageType.ERROR)
        return FakeReply([value])

    bodies: dict[str, list[Any]] = {
        "ListUnits": [SAMPLE_UNITS],
        "ListUnitFiles": [SAMPLE_UNIT_FILES],
        "ListJobs": [SAMPLE_JOBS],
        "ListSessions": [SAMPLE_SESSIONS],
        "LoadUnit": [UNIT_PATH],
        "StartUnit": ["/job/1"],
        "StopUnit": ["/job/2"],
        "RestartUnit": ["/job/3"],
        "ReloadUnit": ["/job/4"],
        "Reload": [],
        "EnableUnitFiles": [True, SAMPLE_CHANGES],
        "DisableUnitFiles": [SAMPLE_CHANGES],
        "MaskUnitFiles": [SAMPLE_CHANGES],
        "UnmaskUnitFiles": [SAMPLE_CHANGES],
    }
    if msg.member not in bodies:
        raise AssertionError(f"unexpected D-Bus call: {msg.interface}.{msg.member}")
    return FakeReply(bodies[msg.member])


class FakeStream:
    """An async byte stream that yields `total` bytes of `line`, built lazily.

    Lazy so a test can push tens of MB through journal_query without the fake
    itself holding them — which is what lets a memory budget see the reader.
    """

    def __init__(self, line: bytes = b"", total: int = 0) -> None:
        self._line = line
        self._left = total if line else 0

    async def read(self, n: int = -1) -> bytes:
        if self._left <= 0:
            return b""
        size = self._left if n < 0 else min(n, self._left)
        reps = size // len(self._line) + 1
        self._left -= size
        return (self._line * reps)[:size]


class FakeProc:
    """A journalctl process: streams for the new reader, communicate() for the old."""

    def __init__(
        self,
        stdout: bytes = b"",
        total: int | None = None,
        returncode: int = 0,
        stderr: bytes = b"",
        stderr_total: int | None = None,
    ) -> None:
        self.stdout = FakeStream(stdout, len(stdout) if total is None else total)
        self.stderr = FakeStream(stderr, len(stderr) if stderr_total is None else stderr_total)
        self.returncode = returncode

    async def wait(self) -> int:
        return self.returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        out = bytearray()
        while chunk := await self.stdout.read():
            out += chunk
        return bytes(out), b""


class FakeBus:
    """Minimal async stand-in for dbus_fast.aio.MessageBus."""

    def __init__(self, handler: Any = default_handler):
        self.handler = handler
        self.calls: list[Any] = []
        self.disconnected = False

    async def call(self, msg: Any) -> FakeReply:
        self.calls.append(msg)
        return self.handler(msg)

    def disconnect(self) -> None:
        self.disconnected = True

    def members(self) -> list[str]:
        """Method names called on this bus, in order."""
        return [m.member for m in self.calls]


@pytest.fixture
def fake_bus(monkeypatch: pytest.MonkeyPatch) -> FakeBus:
    """Replace dbus_client._get_bus with a FakeBus and hand it to the test."""
    bus = FakeBus()

    async def _get_bus() -> FakeBus:
        return bus

    monkeypatch.setattr(dbus_client, "_get_bus", _get_bus)
    return bus


@pytest.fixture(autouse=True)
def clean_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    """Reset the config singleton and point unit writes at a temp directory."""
    unit_dir = tmp_path / "systemd"
    unit_dir.mkdir()
    monkeypatch.setenv("SYSTEMD_UNIT_DIR", str(unit_dir))
    monkeypatch.delenv("SYSTEMD_EXTRA_PROTECTED_UNITS", raising=False)
    monkeypatch.setattr(config_module, "_config", None)
