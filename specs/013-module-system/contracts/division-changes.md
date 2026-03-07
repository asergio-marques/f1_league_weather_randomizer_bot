# Command Contract: Division Command Changes

**Feature**: 013-module-system  
**Cog**: `src/cogs/season_cog.py` (existing — changes only)

---

## Overview

This document describes only the **changes** to existing division-related commands
required by FR-012 (forecast channel conditionality). No new commands are added.

---

## Changed: `division add`

### Pre-013 Signature
```
/season division add <name> <role> <forecast_channel> [tier]
```

### Post-013 Signature
```
/season division add <name> <role> [forecast_channel] [tier]
```

`forecast_channel` becomes an **optional** parameter.

### New Validation Logic

After resolving the parameter, apply mutual-exclusivity rules:

```
weather_enabled = ModuleService.is_enabled(server_id, "weather")

if weather_enabled and forecast_channel is None:
    → Error: "Weather module is active — a forecast channel is required for each division."

if not weather_enabled and forecast_channel is not None:
    → Error: "Weather module is inactive — do not configure a forecast channel yet. Enable the weather module first."
```

All other existing validation (name uniqueness, role validity) is unchanged.

### Model Impact
- `Division.forecast_channel_id: int | None` — `None` stored as `NULL` in DB.

---

## Changed: `division duplicate`

Applies the same mutual-exclusivity guard as `division add`. The duplicated division
inherits its `forecast_channel_id` from the source division; if the source has
`forecast_channel_id = NULL` and the weather module is now enabled (edge case: module
was enabled after the season was set up), the duplicate command must require a
`forecast_channel` argument or fail with the same error.

Practical simplification: apply the same guard — if weather module is enabled and the
inherited value would be NULL, error; if weather module is disabled and a
`forecast_channel` override is supplied, error.

---

## No Changes

The following commands are **not changed** by this feature:
- `/season division rename`
- `/season division remove`
- `/season division list`
- All round-related commands (scheduling is gated at module check in service, not cog)
