# Security Design Document

This document describes the security architecture of mcp-systemd-crunchtools.

## 1. Threat Model

### 1.1 Assets to Protect

| Asset | Sensitivity | Impact if Compromised |
|-------|-------------|----------------------|
| Host D-Bus system bus | Critical | Full control over every systemd unit on the host |
| `/etc/systemd/system` (when mounted) | Critical | Arbitrary unit file write = arbitrary root-privileged process definition |
| Journal contents | Medium | Log data exposure |
| Session/host info | Low | Informational, read-only |

This server has a **larger blast radius than mcp-podman**: mcp-podman is scoped to units whose `ExecStart` contains `/usr/bin/podman`, so a bug or a bad prompt can only touch containers. mcp-systemd operates on any systemd unit, including the ones that keep the host reachable (sshd, networking, D-Bus itself).

### 1.2 Attack Vectors

| Vector | Description | Mitigation |
|--------|-------------|------------|
| **Core-service disruption** | Stopping/disabling/masking sshd, D-Bus, networking, or logind | Protected-unit denylist, not bypassable for the built-in set |
| **Unit name injection / path traversal** | A crafted unit name escaping `SYSTEMD_UNIT_DIR` or targeting an arbitrary D-Bus path | Regex validation (`models.UNIT_NAME_PATTERN`) rejects anything but a bare `name.suffix`; `_resolve_unit_path` re-checks the resolved path's parent |
| **Unintentional data loss on overwrite/removal** | `unit_file_write` overwriting or `unit_file_remove` deleting a unit file | Both always copy the existing file to a timestamped backup before touching it |
| **Persistent host compromise via unit file write** | Writing a unit file with a malicious `ExecStart` (runs as whatever user manages that unit dir, often root) | No built-in privilege escalation beyond what the mounted D-Bus/filesystem access already grants; this is why the unit-dir mount is optional and separate from the D-Bus mount |
| **Resource exhaustion** | Restarting units in a loop | No rate limiting — rely on the MCP client's confirmation prompts |
| **Supply Chain** | Compromised dependencies | Automated CVE scanning |

## 2. Security Architecture

### 2.1 Defense in Depth

- **Layer 1 — Input Validation:** unit-name regex rejects paths/traversal; Pydantic `UnitFileWriteInput` enforces `extra="forbid"` and size limits
- **Layer 2 — Protected-Unit Denylist:** hardcoded core-unit list, extendable but never shrinkable at runtime
- **Layer 3 — Backup-Before-Mutate:** every unit-file write or removal preserves the prior version
- **Layer 4 — Socket/Mount Scoping:** D-Bus socket and unit directory are separate, optional mounts — deployments that only need read/lifecycle tools never grant filesystem write access
- **Layer 5 — Supply Chain:** weekly automated CVE scanning, Hummingbird base images

### 2.2 Authentication

Like mcp-podman, this server uses **Unix socket file permissions** for authentication against the host D-Bus bus — no API token. Whatever privilege the mounted socket grants (typically root, since unit lifecycle operations require it) is the server's privilege. The protected-unit denylist and unit-name validation are the only guardrails on top of that.

### 2.3 SELinux

When running in a container with the host D-Bus socket and unit directory mounted:
- Use `--security-opt label=type:container_runtime_t`
- Mount both paths with `:Z`/`:z` relabel flags as appropriate

## 3. Reporting Security Issues

Report vulnerabilities using [GitHub's private security advisory](https://github.com/crunchtools/mcp-systemd/security/advisories/new).

Do NOT open public issues for security vulnerabilities.
