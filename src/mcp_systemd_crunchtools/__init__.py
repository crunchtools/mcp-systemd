"""MCP Systemd CrunchTools - MCP server for systemd unit management via D-Bus.

Manages the full lifecycle of any systemd unit: listing, status, start/stop/
restart/reload, enable/disable/mask, unit file write and decommission,
journal queries, failed-unit and pending-job triage, timers, host info, and
login sessions.

Usage:
    mcp-systemd-crunchtools
    python -m mcp_systemd_crunchtools
    uvx mcp-systemd-crunchtools

Environment Variables:
    DBUS_SYSTEM_BUS_SOCKET: Optional. Path to the D-Bus system bus socket
        (default: /run/dbus/system_bus_socket).
    SYSTEMD_UNIT_DIR: Optional. Directory unit_file_write/unit_file_remove
        operate on (default: /etc/systemd/system).
    SYSTEMD_EXTRA_PROTECTED_UNITS: Optional. Comma-separated unit names added
        to the built-in protected-unit denylist.

Example with Claude Code:
    claude mcp add mcp-systemd-crunchtools \\
        -- uvx mcp-systemd-crunchtools
"""

import argparse

from .server import mcp

__version__ = "0.1.0"
__all__ = ["main", "mcp"]


def main() -> None:
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="MCP server for systemd")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to for HTTP transports (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8024,
        help="Port to bind to for HTTP transports (default: 8024)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port)
