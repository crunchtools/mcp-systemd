# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/).

Entries prior to 2026-09-19 are back-filled from GitHub Release notes (RT #1484).

## [Unreleased]

## [0.1.0] - 2026-09-19

First working release of mcp-systemd-crunchtools. Serves streamable-http on port
**8022**.

### Added
- 21 systemd D-Bus tools split out of `mcp-podman` (RT #1465): unit queries,
  lifecycle, unit-file state, unit-file write/remove, journal, jobs, timers,
  sessions, host and system status.

### Security
- Unlike the `service_*` tools they replace, these are not restricted to units
  whose `ExecStart` mentions `/usr/bin/podman`. The wider scope is guarded by a
  protected-unit denylist instead (`SYSTEMD_EXTRA_PROTECTED_UNITS` extends it,
  never shrinks it).
