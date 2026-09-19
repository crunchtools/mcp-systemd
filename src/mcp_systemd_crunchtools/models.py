"""Validation constants and Pydantic models for write operations."""

import re

from pydantic import BaseModel, ConfigDict, Field

MAX_UNIT_NAME_LENGTH = 255
MAX_UNIT_FILE_BYTES = 65536
MAX_PATTERN_LENGTH = 200

# Bare unit name only — no slashes, no leading dot, a recognized unit suffix.
# This blocks path traversal (../, absolute paths) by construction.
# \Z, not $: $ also matches before a trailing newline, which would let
# "myapp.service\n" through and smuggle a newline into a written filename.
UNIT_NAME_PATTERN = re.compile(
    r"^[A-Za-z0-9_.:\\@-]+\.(service|socket|target|timer|mount|automount|swap|path|slice|scope)\Z"
)

ALLOWED_JOURNAL_PRIORITIES = {
    "emerg", "alert", "crit", "err", "warning", "notice", "info", "debug",
    "0", "1", "2", "3", "4", "5", "6", "7",
}

DEFAULT_PROTECTED_UNITS = frozenset({
    "dbus.service",
    "dbus-broker.service",
    "systemd-logind.service",
    "systemd-journald.service",
    "systemd-networkd.service",
    "systemd-resolved.service",
    "sshd.service",
    "ssh.service",
    "network.service",
    "NetworkManager.service",
    "polkit.service",
})


class UnitFileWriteInput(BaseModel):
    """Validated input for writing a systemd unit file to disk."""

    model_config = ConfigDict(extra="forbid")

    unit_name: str = Field(
        ..., min_length=1, max_length=MAX_UNIT_NAME_LENGTH,
        description="Bare unit file name, e.g. 'myapp.service'",
    )
    content: str = Field(
        ..., min_length=1, max_length=MAX_UNIT_FILE_BYTES,
        description="Full contents of the unit file",
    )
    enable: bool = Field(default=False, description="Enable the unit after writing")
    start: bool = Field(default=False, description="Start the unit after writing")
