"""Safe error types for the systemd MCP server.

All errors inherit from ToolError so FastMCP returns them as tool errors
rather than crashing the server.

Error messages echo back a caller-supplied name, so every name is truncated
before it reaches a log or a tool response: MAX_NAME_CHARS for unit names,
MAX_REF_CHARS for longer references (patterns, paths).
"""

import logging

from fastmcp.exceptions import ToolError

logger = logging.getLogger(__name__)

MAX_NAME_CHARS = 80
MAX_REF_CHARS = 200


class ConfigurationError(ToolError):
    """Server configuration is invalid."""


class InvalidUnitNameError(ToolError):
    """Unit name failed format validation."""

    def __init__(self, name: str) -> None:
        safe_name = name[:MAX_NAME_CHARS]
        super().__init__(
            f"Invalid unit name: {safe_name!r}. Must be a bare systemd unit name "
            "(e.g. 'myapp.service'), not a path."
        )


class UnitNotFoundError(ToolError):
    """Systemd unit does not exist."""

    def __init__(self, name: str) -> None:
        safe_name = name[:MAX_NAME_CHARS]
        super().__init__(f"Systemd unit not found: {safe_name}")


class ProtectedUnitError(ToolError):
    """Unit is on the protected list and cannot be stopped/disabled/removed."""

    def __init__(self, name: str, action: str) -> None:
        safe_name = name[:MAX_NAME_CHARS]
        super().__init__(
            f"Refusing to {action} '{safe_name}': it is on the protected-unit list "
            "(core system services). Set SYSTEMD_EXTRA_PROTECTED_UNITS to add more "
            "units, but this list cannot be bypassed for the built-in defaults."
        )


class InvalidJournalPriorityError(ToolError):
    """Journal priority is not one of the values journalctl accepts."""

    def __init__(self, priority: str) -> None:
        safe_priority = priority[:MAX_NAME_CHARS]
        super().__init__(
            f"Invalid journal priority: {safe_priority!r}. Use one of "
            "emerg/alert/crit/err/warning/notice/info/debug or 0-7."
        )


class UnitOperationError(ToolError):
    """A systemd D-Bus operation failed."""


class UnitFileError(ToolError):
    """Reading, writing, or removing a unit file on disk failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message[:MAX_REF_CHARS])
