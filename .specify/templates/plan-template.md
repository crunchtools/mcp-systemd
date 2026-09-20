# Implementation Plan: [Feature Name]

> **Spec ID:** XXX-feature-name
> **Status:** Planning | In Progress | Complete
> **Last Updated:** YYYY-MM-DD

## Summary

[1-2 sentence summary of implementation approach]

---

## Architecture

### Tool Flow

```
Claude Code / AI Client
    │
    ▼
server.py (@mcp.tool, "_tool" suffix)
    │ validates args, delegates
    ▼
tools/group.py (thin async pass-through)
    │
    ▼
dbus_client.py (D-Bus wire logic / filesystem I/O)
    │
    ▼
org.freedesktop.systemd1 (D-Bus system bus) or /etc/systemd/system (disk)
```

### Data Flow

1. [Step 1]
2. [Step 2]
3. [Step 3]

---

## Implementation Steps

### Phase 1: Validation / Models (if needed)

- [ ] Add or update Pydantic models in `models.py`
- [ ] Add constants for field limits

### Phase 2: Wire Logic

- [ ] Add/update async functions in `dbus_client.py`

### Phase 3: Tool Functions

- [ ] Add/update thin pass-through in `tools/*.py`
- [ ] Update exports in `tools/__init__.py`

### Phase 4: Server Registration

- [ ] Import in `server.py`
- [ ] Add/update `@mcp.tool()` wrapper, validate args before delegating

### Phase 5: Tests

- [ ] Add mocked D-Bus tests in `test_tools.py` (use `fake_bus` fixture)
- [ ] Add validation tests in `test_validation.py`
- [ ] Update `EXPECTED_TOOL_COUNT` if the tool count changed

### Phase 6: Quality Gates

- [ ] `uv run ruff check src tests`
- [ ] `uv run mypy src`
- [ ] `uv run pytest -v`
- [ ] `gourmand --full .`
- [ ] `podman build -f Containerfile .`

---

## File Changes

### New Files

| File | Purpose |
|------|---------|
| — | — |

### Modified Files

| File | Changes |
|------|---------|
| `models.py` | [Description] |
| `server.py` | [Description] |
| `errors.py` | [Description] |
| `tests/test_tools.py` | [Description] |
| `tests/test_validation.py` | [Description] |

---

## Testing Strategy

### Mocked Tests

- [ ] Valid input passes through to `dbus_client` unchanged
- [ ] Each rejected-input case raises the expected, safely-truncated error
- [ ] Existing D-Bus wire-logic tests (`fake_bus`) still pass unmodified

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| [Risk 1] | [High/Med/Low] | [How to mitigate] |

---

## Changelog

| Date | Changes |
|------|---------|
| YYYY-MM-DD | Initial plan |
