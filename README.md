# mcp-systemd-crunchtools

<!-- mcp-name: io.github.crunchtools/systemd -->

MCP server for systemd unit management via D-Bus. Manages the full lifecycle of any systemd unit — not just Podman-managed containers: listing, status, lifecycle control, unit file authoring and decommissioning, journal queries, failed-unit and job triage, timers, host info, and login sessions.

## Installation

```bash
# uvx (zero-install)
uvx mcp-systemd-crunchtools

# pip
pip install mcp-systemd-crunchtools

# Container
podman run \
  -v /run/dbus/system_bus_socket:/run/dbus/system_bus_socket \
  -v /etc/systemd/system:/etc/systemd/system:Z \
  --security-opt label=type:container_runtime_t \
  quay.io/crunchtools/mcp-systemd
```

The D-Bus socket mount is required for every tool. The `/etc/systemd/system` mount is only required for `unit_file_write_tool` and `unit_file_remove_tool` — omit it to run the server read/lifecycle-only.

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DBUS_SYSTEM_BUS_SOCKET` | No | `/run/dbus/system_bus_socket` | D-Bus system bus socket path |
| `SYSTEMD_UNIT_DIR` | No | `/etc/systemd/system` | Directory unit_file_write/remove operate on |
| `SYSTEMD_EXTRA_PROTECTED_UNITS` | No | — | Comma-separated units added to the built-in denylist |

## Protected units

`unit_stop`, `unit_restart`, `unit_disable`, `unit_mask`, and `unit_file_remove` refuse to act on a small built-in denylist of core system units (dbus, sshd, networking, logind, journald). This cannot be bypassed — it exists so an agent can't take down the box it's running on. Add more units with `SYSTEMD_EXTRA_PROTECTED_UNITS`.

## Claude Code Integration

```bash
claude mcp add mcp-systemd-crunchtools \
  -- uvx mcp-systemd-crunchtools
```

## Tools (21)

### Units (3)
| Tool | Description |
|------|-------------|
| `unit_list` | List loaded units or installed unit files |
| `unit_status` | Curated status (active state, PID, memory, CPU) |
| `unit_show` | Full property dump (deps, exec settings, cgroup) |

### Lifecycle (9)
| Tool | Description |
|------|-------------|
| `unit_start` | Start a unit |
| `unit_stop` | Stop a unit (protected-list guarded) |
| `unit_restart` | Restart a unit (protected-list guarded) |
| `unit_reload` | Reload a unit's config without restarting |
| `unit_enable` | Enable a unit to start on boot |
| `unit_disable` | Disable a unit from starting on boot (protected-list guarded) |
| `unit_mask` | Mask a unit (protected-list guarded) |
| `unit_unmask` | Unmask a unit |
| `daemon_reload` | Reload systemd's unit file cache |

### Unit files (2)
| Tool | Description |
|------|-------------|
| `unit_file_write` | Write a new unit file (backs up any file it overwrites) |
| `unit_file_remove` | Decommission: stop, disable, back up, remove (protected-list guarded) |

### Troubleshooting (3)
| Tool | Description |
|------|-------------|
| `journal_query` | Filtered journal query (unit, priority, since/until, pattern, boot) |
| `failed_units` | List units in the 'failed' state |
| `list_jobs` | List pending/stuck jobs |

### Timers (1)
| Tool | Description |
|------|-------------|
| `timer_list` | List timers with next/last elapse |

### System (2)
| Tool | Description |
|------|-------------|
| `system_status` | Manager state: running/degraded, failed/job counts, version |
| `hostinfo` | Hostname, kernel, OS |

### Sessions (1)
| Tool | Description |
|------|-------------|
| `session_list` | Who's logged in right now |

## License

AGPL-3.0-or-later
