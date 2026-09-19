# mcp-systemd-crunchtools

MCP server for systemd unit management via D-Bus (system bus), plus journalctl for filtered log queries (no D-Bus equivalent exists for arbitrary journal filters).

## Quick Start

```bash
uv sync --all-extras
uv run pytest -v
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DBUS_SYSTEM_BUS_SOCKET` | No | `/run/dbus/system_bus_socket` | D-Bus system bus socket path |
| `SYSTEMD_UNIT_DIR` | No | `/etc/systemd/system` | Directory unit_file_write/remove operate on |
| `SYSTEMD_EXTRA_PROTECTED_UNITS` | No | — | Comma-separated units added to the built-in denylist |

## Tools (21)

### Units (3)
unit_list, unit_status, unit_show

### Lifecycle (9)
unit_start, unit_stop, unit_restart, unit_reload, unit_enable, unit_disable, unit_mask, unit_unmask, daemon_reload

### Unit files (2) — highest blast radius, writes/deletes host files
unit_file_write, unit_file_remove

### Troubleshooting (3)
journal_query, failed_units, list_jobs

### Timers (1)
timer_list

### System (2)
system_status, hostinfo

### Sessions (1)
session_list

## Development Commands

```bash
uv run ruff check src tests       # Lint
uv run mypy src                    # Type check
uv run pytest -v                   # Tests
gourmand --full .                  # AI slop detection
podman build -f Containerfile .    # Container build
```

## Architecture

Two-layer tool pattern:
- `server.py` — `@mcp.tool()` wrappers with `_tool` suffix
- `tools/*.py` — thin pass-through async functions grouped by domain, calling `dbus_client.py`
- `dbus_client.py` — all D-Bus wire logic (systemd1 Manager/Unit/Service/Timer, hostname1, login1) plus the journalctl subprocess call and unit-file disk I/O

## Safety model

This server supersedes mcp-podman's old `service_*` tools and operates on **any** systemd unit, not just Podman-managed ones — split out per RT #1465. Three layers keep that broad scope from being a foot-gun:

1. **Unit name validation** (`models.UNIT_NAME_PATTERN`) — bare names only, no paths, no traversal. Rejects anything that isn't `name.suffix` with a recognized systemd unit suffix.
2. **Protected-unit denylist** (`config.DEFAULT_PROTECTED_UNITS`, extendable via `SYSTEMD_EXTRA_PROTECTED_UNITS`) — blocks `stop`/`restart`/`disable`/`mask`/`unit_file_remove` on core units (dbus, sshd, networking, logind, journald) so an agent can't take down the box it's running on. Never bypassable for the built-in set.
3. **Backup-before-write** — `unit_file_write` and `unit_file_remove` always copy the existing file to `<name>.bak-<timestamp>` alongside the original before overwriting or deleting it.

`unit_file_write`/`unit_file_remove` require the host's `SYSTEMD_UNIT_DIR` bind-mounted into the container; every other tool only needs the D-Bus socket.
