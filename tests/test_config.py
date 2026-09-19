"""Configuration and D-Bus socket validation tests."""

from pathlib import Path

import pytest

from mcp_systemd_crunchtools.config import (
    DEFAULT_DBUS_SOCKET,
    DEFAULT_UNIT_DIR,
    Config,
    get_config,
    validate_dbus_socket,
)
from mcp_systemd_crunchtools.errors import ConfigurationError
from mcp_systemd_crunchtools.models import DEFAULT_PROTECTED_UNITS


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DBUS_SYSTEM_BUS_SOCKET", raising=False)
    monkeypatch.delenv("SYSTEMD_UNIT_DIR", raising=False)
    config = Config()
    assert config.dbus_socket == DEFAULT_DBUS_SOCKET
    assert config.unit_dir == DEFAULT_UNIT_DIR


def test_env_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DBUS_SYSTEM_BUS_SOCKET", "/tmp/bus")
    monkeypatch.setenv("SYSTEMD_UNIT_DIR", str(tmp_path))
    config = Config()
    assert config.dbus_socket == "/tmp/bus"
    assert config.unit_dir == str(tmp_path)


def test_extra_protected_units_are_added(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYSTEMD_EXTRA_PROTECTED_UNITS", "critical.service, other.timer ,")
    config = Config()
    assert "critical.service" in config.protected_units
    assert "other.timer" in config.protected_units
    assert "" not in config.protected_units


def test_defaults_cannot_be_removed_by_the_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """SYSTEMD_EXTRA_PROTECTED_UNITS extends the denylist — it never shrinks it."""
    monkeypatch.setenv("SYSTEMD_EXTRA_PROTECTED_UNITS", "only-this.service")
    assert Config().protected_units >= DEFAULT_PROTECTED_UNITS


def test_get_config_is_a_singleton() -> None:
    assert get_config() is get_config()


def test_repr_does_not_leak_anything_unexpected() -> None:
    assert "unit_dir" in repr(get_config())


def test_validate_dbus_socket_accepts_an_existing_path(tmp_path: Path) -> None:
    socket_path = tmp_path / "system_bus_socket"
    socket_path.touch()
    validate_dbus_socket(str(socket_path))


def test_validate_dbus_socket_rejects_a_missing_path(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="not found"):
        validate_dbus_socket(str(tmp_path / "nope"))
