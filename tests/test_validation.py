"""Input validation tests — the first of the five security layers."""

import pytest
from pydantic import ValidationError

from mcp_systemd_crunchtools.dbus_client import assert_not_protected, validate_unit_name
from mcp_systemd_crunchtools.errors import InvalidUnitNameError, ProtectedUnitError
from mcp_systemd_crunchtools.models import (
    MAX_UNIT_FILE_BYTES,
    MAX_UNIT_NAME_LENGTH,
    UnitFileWriteInput,
)


class TestUnitNameValidation:
    @pytest.mark.parametrize(
        "name",
        [
            "myapp.service",
            "mcp-podman.service",
            "systemd-journald.socket",
            "multi-user.target",
            "backup.timer",
            "var-lib-containers.mount",
            "user@1000.service",
            "user.slice",
            "session-3.scope",
            "dev-disk-by\\x2duuid.swap",
            "run-user-1000.automount",
            "systemd-ask-password.path",
        ],
    )
    def test_accepts_real_unit_names(self, name: str) -> None:
        assert validate_unit_name(name) == name

    @pytest.mark.parametrize(
        "name",
        [
            "../../etc/passwd",
            "../evil.service",
            "/etc/systemd/system/evil.service",
            "sub/dir/myapp.service",
            "myapp.service\n[Service]",
            "myapp.service\n",
            "myapp.service; rm -rf /",
            "myapp",
            "myapp.conf",
            "myapp.service.bak",
            "",
            ".service",
            "$(whoami).service",
            "my app.service",
        ],
    )
    def test_rejects_anything_that_is_not_a_bare_unit_name(self, name: str) -> None:
        with pytest.raises(InvalidUnitNameError):
            validate_unit_name(name)

    def test_error_message_truncates_a_long_name(self) -> None:
        with pytest.raises(InvalidUnitNameError) as exc:
            validate_unit_name("/" + "a" * 5000)
        assert len(str(exc.value)) < 300


class TestProtectedUnits:
    @pytest.mark.parametrize(
        "name",
        ["sshd.service", "dbus.service", "systemd-journald.service", "NetworkManager.service"],
    )
    def test_core_units_are_protected(self, name: str) -> None:
        with pytest.raises(ProtectedUnitError):
            assert_not_protected(name, "stop")

    def test_ordinary_units_are_not_protected(self) -> None:
        assert_not_protected("myapp.service", "stop")  # does not raise


class TestUnitFileWriteInput:
    def test_minimal_valid_input(self) -> None:
        model = UnitFileWriteInput(unit_name="myapp.service", content="[Unit]\n")
        assert model.enable is False
        assert model.start is False

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            UnitFileWriteInput(unit_name="myapp.service", content="[Unit]\n", path="/etc")

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"unit_name": "", "content": "[Unit]\n"},
            {"unit_name": "myapp.service", "content": ""},
            {"unit_name": "a" * (MAX_UNIT_NAME_LENGTH + 1), "content": "[Unit]\n"},
            {"unit_name": "myapp.service", "content": "x" * (MAX_UNIT_FILE_BYTES + 1)},
        ],
    )
    def test_rejects_empty_and_oversized_values(self, kwargs: dict[str, str]) -> None:
        with pytest.raises(ValidationError):
            UnitFileWriteInput(**kwargs)
