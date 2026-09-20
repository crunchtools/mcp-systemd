# Specification: Wire UnitFileWriteInput into unit_file_write_tool

> **Spec ID:** 001-unit-file-write-validation
> **Status:** Implemented
> **Version:** 0.1.0
> **Author:** Scott McCarty
> **Date:** 2026-09-20

## Overview

`UnitFileWriteInput` (`models.py`) declares the Layer 2 input-validation
contract for the highest-blast-radius tool in the fleet — `extra="forbid"`,
non-empty `unit_name`/`content`, and length caps (`MAX_UNIT_NAME_LENGTH=255`,
`MAX_UNIT_FILE_BYTES=65536`) — and is fully tested in `test_validation.py`.
It is never instantiated in production: `unit_file_write_tool` takes raw
args and only the unit *name* is validated (format, via
`dbus_client.validate_unit_name`), so content size/emptiness and unexpected
fields are enforced by nothing the running server executes. This closes
RT #1492, filed against the Gourmand 1.0.0 migration (RT #1482,
finding DC004-dead_structs at `models.py:39`).

---

## New / Changed Tools

No new tools. `unit_file_write_tool`'s external signature and behavior on
valid input are unchanged.

| Tool | Change |
|------|--------|
| `unit_file_write_tool` | Now validates `(unit_name, content, enable, start)` through `UnitFileWriteInput` before delegating. |

---

## Security Considerations

### Layer 1 — Credential Protection
Not applicable — no credentials involved.

### Layer 2 — Input Validation
`unit_file_write_tool` constructs `UnitFileWriteInput(unit_name=..., content=..., enable=..., start=...)`
before calling `tools.unit_file_write`. A `pydantic.ValidationError` is caught
and re-raised as a new `UnitFileValidationError(ToolError)` so FastMCP
returns a tool error instead of an unhandled exception, and so the message
follows the same truncate-before-surfacing convention as every other error
in `errors.py`. This makes the model's existing tests (`TestUnitFileWriteInput`
in `test_validation.py`) meaningful: they now describe behavior the running
server actually has.

`dbus_client.validate_unit_name` (unit-name *format*, via `UNIT_NAME_PATTERN`)
still runs unchanged inside `dbus_client.unit_file_write` — this spec adds a
size/shape check in front of it, it does not replace it.

### Layer 3 — Protected-Unit Denylist
Not applicable — `unit_file_write` was never denylist-gated (only
`unit_file_remove` and the lifecycle-mutation tools are); this is unchanged.

### Layer 4 — Backup Before Mutate
Unaffected. Backup-before-write in `dbus_client.unit_file_write` runs only
after validation now passes, same as before.

### Layer 5 — Supply Chain Security
No new dependency — `pydantic` is already a direct dependency.

---

## Module Changes

### New Files

None.

### Modified Files

| File | Changes |
|------|---------|
| `server.py` | `unit_file_write_tool` validates via `UnitFileWriteInput` before delegating to `tools.unit_file_write`. |
| `errors.py` | New `UnitFileValidationError(ToolError)` — formats a `pydantic.ValidationError` into a safe, truncated message. |
| `tests/test_tools.py` | New test class exercising `server.unit_file_write_tool` directly: valid input passes through, each invalid case raises `UnitFileValidationError`. |

`models.py` and `dbus_client.py` are unchanged — the model and the
lower-layer validation already existed; only the missing wire-up is added.

---

## Behavior Change

Previously silently accepted requests now raise `UnitFileValidationError`
instead of being written to disk:

- Empty `unit_name` or empty `content`
- `unit_name` over 255 characters or `content` over 65536 characters
- Any extra/unrecognized field in the tool call

This is a narrowing of accepted input on the single highest-blast-radius
tool in the server (it writes files to the host's systemd unit directory).
No previously-rejected input becomes newly accepted.

---

## Testing Requirements

### Mocked D-Bus Tests
- [x] `TestUnitFileWriteToolValidation` class in `test_tools.py`, using the `fake_bus` fixture
- [x] Valid input still writes the file and reloads (regression check)
- [x] Each rejected case (empty name, empty content, oversized name, oversized content, extra field) raises `UnitFileValidationError` and performs no D-Bus call and no disk write

### Input Validation Tests
- [x] `TestUnitFileWriteInput` in `test_validation.py` already covers the model itself — unchanged

### Tool Count Update
- [x] Not applicable — no tool added or removed (`EXPECTED_TOOL_COUNT` unchanged)

---

## Dependencies

- Depends on: RT #1482 (Gourmand 1.0.0 migration, which surfaced this as `fix_planned`)
- Blocks: nothing

---

## Open Questions

None — the ticket's own analysis and recommendation (option 1) fully
specify the fix.

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-09-20 | Initial draft, implemented same day |
