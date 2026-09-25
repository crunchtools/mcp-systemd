# mcp-systemd-crunchtools Constitution

> **Version:** 0.1.1
> **Ratified:** 2026-09-19
> **Status:** Active
> **Inherits:** [crunchtools/constitution](https://github.com/crunchtools/constitution) v1.17.0
> **Profile:** MCP Server

This constitution establishes the core principles, constraints, and workflows that govern all development on mcp-systemd-crunchtools.

---

## I. Core Principles

### 1. Five-Layer Security Model

Every change MUST preserve all five security layers. No exceptions.

**Layer 1 — Credential Protection:**
- This server uses D-Bus system bus socket file permissions for authentication — no API tokens
- Socket path loaded from `DBUS_SYSTEM_BUS_SOCKET` (default `/run/dbus/system_bus_socket`)
- There are no Pydantic `SecretStr` fields today because the server holds no secret. If a
  credential is ever introduced (a remote bus, an auth proxy), it MUST be typed `SecretStr`,
  MUST come from the environment, and MUST never be logged or returned in a tool response

**Layer 2 — Input Validation:**
- Unit names validated against `UNIT_NAME_PATTERN` before every D-Bus call and every filesystem path resolution — no paths, no traversal
- Pydantic models enforce strict data types with `extra="forbid"` for compound write inputs
- Field length limits on all user-provided strings

**Layer 3 — Protected-Unit Denylist:**
- `stop`, `restart`, `disable`, `mask`, and `unit_file_remove` refuse to act on a hardcoded set of core system units (dbus, sshd, networking, logind, journald)
- Extendable via `SYSTEMD_EXTRA_PROTECTED_UNITS`, never shrinkable at runtime

**Layer 4 — Backup Before Mutate:**
- `unit_file_write` and `unit_file_remove` always copy the file they are about to overwrite or delete to a timestamped backup alongside it before touching it

**Layer 5 — Supply Chain Security:**
- Weekly automated CVE scanning via GitHub Actions
- Hummingbird container base images (minimal CVE surface)
- Gourmand AI slop detection gating all PRs

### 2. Two-Layer Tool Architecture

Tools follow a strict two-layer pattern:
- `server.py` — `@mcp.tool()` decorated functions that validate args and delegate
- `tools/*.py` — thin async pass-through functions grouped by domain, calling `dbus_client.py`
- `dbus_client.py` — all D-Bus wire logic plus journalctl subprocess calls and unit-file disk I/O

Never put business logic in `server.py`. Never put MCP registration in `tools/*.py`.

### 3. Scope: Any Unit, Not Just Podman

Unlike the `service_*` tools this server superseded in mcp-podman-crunchtools (RT #1465), mcp-systemd-crunchtools operates on **any** systemd unit. The protected-unit denylist is what keeps that scope safe, not a Podman-only `ExecStart` filter.

### 4. Three Distribution Channels

Every release MUST be available through all three channels simultaneously:

| Channel | Command | Use Case |
|---------|---------|----------|
| uvx | `uvx mcp-systemd-crunchtools` | Zero-install, Claude Code |
| pip | `pip install mcp-systemd-crunchtools` | Virtual environments |
| Container | `podman run quay.io/crunchtools/mcp-systemd` | Isolated, systemd |

### 5. Three Transport Modes

The server MUST support all three MCP transports:
- **stdio** (default) — spawned per-session by Claude Code
- **SSE** — legacy HTTP transport
- **streamable-http** — production HTTP, systemd-managed containers

### 6. Semantic Versioning

Follow [Semantic Versioning 2.0.0](https://semver.org/) strictly.

**MAJOR** (breaking changes): Removed/renamed tools, changed parameters
**MINOR** (new functionality): New tools, new optional parameters
**PATCH** (fixes): Bug fixes, security patches, test improvements

### 7. AI Code Quality

All code MUST pass Gourmand checks before merge. Zero violations required.

---

## II. Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Language | Python | 3.10+ |
| MCP Framework | FastMCP | Latest |
| D-Bus Client | dbus-fast | Latest |
| Validation | Pydantic | v2 |
| Container Base | Hummingbird | Latest |
| Package Manager | uv | Latest |
| Build System | hatchling | Latest |
| Linter | ruff | Latest |
| Type Checker | mypy (strict) | Latest |
| Tests | pytest + pytest-asyncio | Latest |
| Slop Detector | gourmand | Latest |

---

## III. Testing Standards

### Mocked D-Bus Tests (MANDATORY)

Every tool MUST have a corresponding mocked test. Tests patch `dbus_client._get_bus` and `dbus_client._call`/`_get_property` — no live D-Bus connection, no host socket required in CI.

**Tool count assertion:** `test_tool_count` MUST be updated whenever tools are added or removed.

### Input Validation Tests

Unit-name validation and `UnitFileWriteInput` MUST have tests in `test_validation.py`:
- Valid minimal input
- Invalid/rejected inputs (path traversal, bad suffix, empty strings, extra fields)

---

## IV. Gourmand (AI Slop Detection)

All code MUST pass `gourmand --full .` with **zero violations** before merge.

### Exception Policy

Exceptions MUST have documented justifications in `gourmand-exceptions.toml`. Acceptable reasons:
- Standard API patterns (assigned port numbers)
- Framework requirements (CLAUDE.md for Claude Code)

---

## V. Code Quality Gates

Every code change must pass through these gates in order:

1. **Lint** — `uv run ruff check src tests`
2. **Type Check** — `uv run mypy src`
3. **Tests** — `uv run pytest -v` (all passing, mocked D-Bus)
4. **Gourmand** — `gourmand --full .` (zero violations)
5. **Container Build** — `podman build -f Containerfile .`

---

## VI. Naming Conventions

| Context | Name |
|---------|------|
| GitHub repo | `crunchtools/mcp-systemd` |
| PyPI package | `mcp-systemd-crunchtools` |
| CLI command | `mcp-systemd-crunchtools` |
| Python module | `mcp_systemd_crunchtools` |
| Container image | `quay.io/crunchtools/mcp-systemd` |
| systemd service | `mcp-systemd.service` |
| HTTP port | 8022 |
| License | AGPL-3.0-or-later |

---

## VII. Development Workflow

### Adding a New Tool

1. Add the async function to `dbus_client.py`
2. Add a thin wrapper to the appropriate `tools/*.py` file and export it from `tools/__init__.py`
3. Import it in `server.py` and register with `@mcp.tool()`
4. Add a mocked test in `tests/test_tools.py`
5. Update the tool count in `test_tool_count`
6. Run all five quality gates
7. Update CLAUDE.md and README.md tool listings

---

## VIII. SELinux and Container Deployment

When running in a container with the host D-Bus socket and/or unit directory mounted:
- Use `--security-opt label=type:container_runtime_t` on the container
- Mount both paths with `:z`/`:Z` relabel flags
- The container runs as `container_runtime_t` domain, which can `connectto` the D-Bus socket

---

## IX. Governance

### Amendment Process

1. Create a PR with proposed changes to this constitution
2. Document rationale in PR description
3. Require maintainer approval
4. Update version number upon merge

### Ratification History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-09-19 | Initial constitution — split from mcp-podman-crunchtools per RT #1465 |
