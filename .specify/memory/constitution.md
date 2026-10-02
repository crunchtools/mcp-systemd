# mcp-systemd-crunchtools Constitution

> **Version:** 0.2.0
> **Ratified:** 2026-09-19
> **Amended:** 2026-10-02
> **Status:** Active
> **Inherits:** [crunchtools/constitution](https://github.com/crunchtools/constitution) v1.18.0
> **Profile:** MCP Server

This file holds what is specific to mcp-systemd. The fleet rules and the MCP
Server profile (five-layer security model, two-layer tools, distribution
channels, transport modes, quality gates, Gourmand) apply at the inherited
version and are checked against this repo's files by `constitution.yml`. They
are not restated here.

## Scope: Any Unit, Not Just Podman

Unlike the `service_*` tools it superseded in mcp-podman-crunchtools
(RT #1465), this server operates on any systemd unit. The protected-unit
denylist below is what keeps that scope safe, not a Podman-only `ExecStart`
filter.

## Security Model Specifics

- **Credentials:** none. Authentication is the D-Bus system bus socket's
  file permissions; the socket path comes from `DBUS_SYSTEM_BUS_SOCKET`
  (default `/run/dbus/system_bus_socket`). There is no `SecretStr` field
  because there is no secret. If a credential is ever introduced (a remote
  bus, an auth proxy), it MUST be `SecretStr`, from the environment, and never
  logged or returned in a tool response.
- **Input limits:** unit names are validated against `UNIT_NAME_PATTERN`
  before every D-Bus call and every filesystem path resolution, so no paths
  and no traversal. Compound write inputs (`UnitFileWriteInput`) use Pydantic
  with `extra="forbid"`.
- **Protected-unit denylist:** `stop`, `restart`, `disable`, `mask` and
  `unit_file_remove` refuse to act on a hardcoded set of core system units
  (dbus, sshd, networking, logind, journald). `SYSTEMD_EXTRA_PROTECTED_UNITS`
  extends the set; nothing shrinks it at runtime.
- **Backup before mutate:** `unit_file_write` and `unit_file_remove` copy the
  file they are about to overwrite or delete to a timestamped backup alongside
  it first.

## Module Layout

`dbus_client.py` holds all D-Bus wire logic, the `journalctl` subprocess calls
and unit-file disk I/O. `tools/*.py` are thin pass-throughs to it, grouped by
domain. Tests patch `dbus_client._get_bus` and `_call`/`_get_property`; no
live D-Bus connection or host socket is needed in CI.

## SELinux and Host Mounts

When the container runs with the host D-Bus socket and/or unit directory
mounted:

- run it with `--security-opt label=type:container_runtime_t`, the domain
  that can `connectto` the D-Bus socket;
- mount both paths with `:z`/`:Z` relabel flags.

## Instance

| Context | Name |
|---------|------|
| GitHub repo | `crunchtools/mcp-systemd` |
| PyPI package | `mcp-systemd-crunchtools` |
| Python module | `mcp_systemd_crunchtools` |
| Container image | `quay.io/crunchtools/mcp-systemd` |
| systemd service | `mcp-systemd.service` |
| HTTP port | 8022 |
| D-Bus client | `dbus-fast` |

## History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-09-19 | Initial constitution, split from mcp-podman-crunchtools per RT #1465 |
| 0.2.0 | 2026-10-02 | Manifest under constitution v1.18.0: profile restatement removed, mcp-systemd specifics kept |
