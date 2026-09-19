"""Unit file lifecycle tools — write new units, decommission old ones.

These are the highest blast-radius tools in the server: they write and
delete files under the host's systemd unit directory. Both back up
whatever they overwrite or remove before touching disk.
"""

from typing import Any

from ..dbus_client import unit_file_remove as _unit_file_remove
from ..dbus_client import unit_file_write as _unit_file_write


async def unit_file_write(
    unit_name: str, content: str, enable: bool = False, start: bool = False,
) -> dict[str, Any]:
    """Write a unit file, backing up any file it overwrites."""
    return await _unit_file_write(unit_name, content, enable=enable, start=start)


async def unit_file_remove(unit_name: str, mask: bool = False) -> dict[str, Any]:
    """Stop, disable, back up, and remove a unit file (decommission helper)."""
    return await _unit_file_remove(unit_name, mask=mask)
