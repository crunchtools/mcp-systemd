# Implementation Plan: Wire UnitFileWriteInput into unit_file_write_tool

> **Spec ID:** 001-unit-file-write-validation
> **Status:** Complete
> **Last Updated:** 2026-09-20

## Summary

Validate `unit_file_write_tool`'s args through the existing `UnitFileWriteInput`
Pydantic model before delegating, converting `pydantic.ValidationError` into
a new safe `UnitFileValidationError`. No new model, no signature change.

---

## Architecture

### Tool Flow

```
Claude Code / AI Client
    │
    ▼
server.py::unit_file_write_tool (@mcp.tool)
    │ UnitFileWriteInput(...) — NEW: raises UnitFileValidationError on bad input
    ▼
tools/files.py::unit_file_write (thin pass-through, unchanged)
    │
    ▼
dbus_client.py::unit_file_write (unit-name format check, backup, write, reload)
    │
    ▼
/etc/systemd/system (disk) + org.freedesktop.systemd1 (D-Bus, daemon-reload)
```

---

## Implementation Steps

### Phase 1: Errors
- [x] Add `UnitFileValidationError(ToolError)` to `errors.py`, built from a `pydantic.ValidationError`, message truncated to `MAX_REF_CHARS`

### Phase 2: Server Registration
- [x] Import `ValidationError` (pydantic) and `UnitFileWriteInput` in `server.py`
- [x] `unit_file_write_tool` validates via `UnitFileWriteInput(...)` before calling `tools.unit_file_write`

### Phase 3: Tests
- [x] New `TestUnitFileWriteToolValidation` in `test_tools.py` calling `server.unit_file_write_tool` directly (per the project's "call the function, not just check the wrapper exists" pattern), with `fake_bus`
- [x] Valid input still writes + reloads
- [x] Each invalid case raises `UnitFileValidationError`, no bus call, no disk write

### Phase 4: Quality Gates
- [x] `uv run ruff check src tests`
- [x] `uv run mypy src`
- [x] `uv run pytest -v`
- [x] `gourmand --full .`
- [x] `podman build -f Containerfile .`

---

## File Changes

| File | Changes |
|------|---------|
| `src/mcp_systemd_crunchtools/errors.py` | New `UnitFileValidationError` |
| `src/mcp_systemd_crunchtools/server.py` | `unit_file_write_tool` validates via `UnitFileWriteInput` |
| `tests/test_tools.py` | New validation test class |

`models.py`, `dbus_client.py`, `tools/files.py` unchanged.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaks an existing caller sending oversized/empty content | Low — no known production caller relies on this; ticket explicitly accepts the behavior change | Documented as an intentional behavior change in the spec |
| pydantic error message leaks unit content in a tool error | Low | Checked: pydantic's length/extra-field errors report field name and constraint, not the value; message is also truncated to `MAX_REF_CHARS` as defense in depth |

---

## Changelog

| Date | Changes |
|------|---------|
| 2026-09-20 | Initial plan, implemented same day |
