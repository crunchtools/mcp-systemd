# Specification: [Feature Name]

> **Spec ID:** XXX-feature-name
> **Status:** Draft | In Progress | Implemented
> **Version:** 0.1.0
> **Author:** [Name]
> **Date:** YYYY-MM-DD

## Overview

[2-3 sentence description of what this feature does and why it matters]

---

## New / Changed Tools

| Tool | D-Bus Interface / Member | Description |
|------|---------------------------|-------------|
| `tool_name_tool` | `org.freedesktop.systemd1.Manager.Method` | [What it does] |

---

## Security Considerations

### Layer 1 — Credential Protection
- [Any change to D-Bus socket auth or credential handling?]

### Layer 2 — Input Validation
- [New or changed Pydantic models needed?]
- [New allowlists, patterns, or field limits?]

### Layer 3 — Protected-Unit Denylist
- [Does this touch stop/restart/disable/mask/unit_file_remove?]

### Layer 4 — Backup Before Mutate
- [Does this write or delete a unit file? Confirm backup-before-write is preserved.]

### Layer 5 — Supply Chain Security
- [Any new dependency?]

---

## Module Changes

### New Files

| File | Purpose |
|------|---------|
| `tools/new_group.py` | [Description] |

### Modified Files

| File | Changes |
|------|---------|
| `models.py` | [New/changed constants or Pydantic models] |
| `server.py` | [Validation wiring, new `@mcp.tool()` wrappers] |
| `tools/*.py` | [Pass-through changes] |
| `dbus_client.py` | [Wire-logic changes] |

---

## Testing Requirements

### Mocked D-Bus Tests
- [ ] New/updated test class in `test_tools.py`
- [ ] One test per behavior change, using the `fake_bus` fixture
- [ ] Error case coverage

### Input Validation Tests
- [ ] New/updated Pydantic model tests in `test_validation.py`
- [ ] Rejection tests (empty, oversized, extra fields, injection)

### Tool Count Update
- [ ] Update `EXPECTED_TOOL_COUNT` in `test_tool_count` if the tool count changed

---

## Dependencies

- Depends on: [Spec ID or external dependency]
- Blocks: [Spec ID that depends on this]

---

## Open Questions

1. [Question that needs resolution before implementation]

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | YYYY-MM-DD | Initial draft |
