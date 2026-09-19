"""Secure configuration from environment variables.

Like mcp-podman-crunchtools, this server has no API token — authentication
is via the host D-Bus system bus socket's Unix file permissions. Config
covers the socket path, the directory unit files may be written to, and
the protected-unit denylist.
"""

import logging
import os
from pathlib import Path

from .errors import ConfigurationError
from .models import DEFAULT_PROTECTED_UNITS

logger = logging.getLogger(__name__)

DEFAULT_DBUS_SOCKET = "/run/dbus/system_bus_socket"
DEFAULT_UNIT_DIR = "/etc/systemd/system"

_config: "Config | None" = None


def get_config() -> "Config":
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


class Config:
    """Systemd MCP server configuration."""

    def __init__(self) -> None:
        self._dbus_socket = os.environ.get("DBUS_SYSTEM_BUS_SOCKET", DEFAULT_DBUS_SOCKET)
        self._unit_dir = os.environ.get("SYSTEMD_UNIT_DIR", DEFAULT_UNIT_DIR)

        extra_raw = os.environ.get("SYSTEMD_EXTRA_PROTECTED_UNITS", "")
        extra_units = frozenset(name.strip() for name in extra_raw.split(",") if name.strip())
        self._protected_units = DEFAULT_PROTECTED_UNITS | extra_units

        unit_dir_path = Path(self._unit_dir)
        if not unit_dir_path.is_dir():
            logger.warning(
                "SYSTEMD_UNIT_DIR %s does not exist in this container. "
                "unit_file_write and unit_file_remove will fail until it is mounted.",
                self._unit_dir,
            )

    @property
    def dbus_socket(self) -> str:
        """Get the D-Bus system bus socket path."""
        return self._dbus_socket

    @property
    def unit_dir(self) -> str:
        """Get the directory unit files are written to and removed from."""
        return self._unit_dir

    @property
    def protected_units(self) -> frozenset[str]:
        """Get the set of unit names that cannot be stopped/disabled/removed."""
        return self._protected_units

    def __repr__(self) -> str:
        return f"Config(unit_dir={self._unit_dir}, dbus_socket={self._dbus_socket})"


def validate_dbus_socket(socket_path: str) -> None:
    """Raise ConfigurationError if the D-Bus socket is missing."""
    path = Path(socket_path)
    if not path.exists():
        raise ConfigurationError(
            f"D-Bus system bus socket not found at {socket_path}. "
            "Mount it into the container: "
            "-v /run/dbus/system_bus_socket:/run/dbus/system_bus_socket"
        )
