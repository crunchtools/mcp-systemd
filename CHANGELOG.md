# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/).

Entries prior to 2026-09-19 are back-filled from GitHub Release notes (RT #1484).

## [Unreleased]

## [0.2.0] - 2026-10-10

### Added
- The ten tools that only read (`unit_list`, `unit_status`, `unit_show`,
  `journal_query`, `failed_units`, `list_jobs`, `timer_list`, `system_status`,
  `hostinfo`, `session_list`) publish `readOnlyHint: true`. A gateway uses it to
  decide whether an invalid optional argument may be dropped or must refuse the
  call (crunchtools/constitution#35). The eleven tools that start, stop, reload,
  enable, mask or write units stay unannotated.
- Tests pin every registered tool into `READ_ONLY` or `WRITES`, and check that a
  read-only tool calls only list/get D-Bus methods, runs `journalctl` with query
  options only, and writes nothing to the unit directory.

### Changed
- Inherits constitution v1.22.0; the workflow pins and the pre-commit hook rev
  move with it.
- Constitution is now a v1.18.0 manifest: only repo-specific facts remain;
  fleet and profile rules apply by reference.
- Constitution validation is pinned via `.github/workflows/constitution.yml`.
- Dependabot auto-merges GitHub Actions minor and patch updates.

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
