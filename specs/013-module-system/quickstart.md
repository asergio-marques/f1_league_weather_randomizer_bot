# Quickstart: Module System (013)

**Feature Branch**: `013-module-system`  
**For**: Implementors picking up tasks from `tasks.md`

---

## What This Feature Does

Adds two per-server modules — **weather** and **signup** — behind explicit admin
enable/disable toggles. Neither module is active by default.

- **Weather module**: gates all weather phase scheduling and execution behind
  `server_configs.weather_module_enabled`. When enabled on an active season,
  runs any overdue phases immediately and schedules future ones.
- **Signup module**: provides a configurable signup channel, role management,
  availability time-slot catalogue, and a signup window open/close lifecycle.

---

## Files to Create

| Path | Purpose |
|------|---------|
| `src/models/signup_module.py` | `SignupModuleConfig`, `SignupModuleSettings`, `AvailabilitySlot` dataclasses |
| `src/services/module_service.py` | Enable/disable logic, DB CRUD for module flags |
| `src/services/signup_module_service.py` | Signup config CRUD, slot CRUD, open/close window |
| `src/cogs/module_cog.py` | `/module enable|disable` command group |
| `src/cogs/signup_cog.py` | `/signup` command group |
| `src/db/migrations/009_module_system.sql` | DB migration (see `data-model.md §1`) |
| `tests/unit/test_module_service.py` | Unit tests for `ModuleService` |
| `tests/unit/test_signup_module_service.py` | Unit tests for `SignupModuleService` |

---

## Files to Modify

| Path | Change |
|------|--------|
| `src/models/division.py` | `forecast_channel_id: int` → `int \| None` |
| `src/models/server_config.py` | Add `weather_module_enabled: bool = False`, `signup_module_enabled: bool = False` |
| `src/services/scheduler_service.py` | Add `cancel_all_weather_for_server(server_id)`; gate `schedule_round()` behind module check |
| `src/services/driver_service.py` | Add two new allowed state transitions (FR-037) |
| `src/cogs/season_cog.py` | Make `forecast_channel` optional in `division add`; add mutual-exclusivity guard |
| `src/bot.py` | Instantiate `ModuleService` and `SignupModuleService`; load new cogs; gate scheduler recovery behind `weather_module_enabled` |
| `src/services/config_service.py` | Map new `server_configs` columns in `get_server_config()` / `save_server_config()` |

---

## Key Design Decisions (summary — see `research.md` for full rationale)

1. **Module state**: two boolean columns on `server_configs` (not a join table).
2. **Signup config**: two separate tables (`signup_module_config`, `signup_module_settings`).
3. **Time slot IDs**: surrogate PK in DB; user-visible 1-based rank computed on read (no stored ID).
4. **Weather catch-up**: sequential synchronous execution inside a deferred interaction response.
5. **Channel permissions**: per-role `PermissionOverwrite`; reversed on module disable.
6. **`forecast_channel` guard**: mutual-exclusivity enforced at command level; module enable pre-validates all divisions.
7. **Cancel weather jobs**: new `cancel_all_weather_for_server()` queries rounds then calls `cancel_round()` per round.
8. **Driver SM**: `PENDING_SIGNUP_COMPLETION → NOT_SIGNED_UP` and `PENDING_DRIVER_CORRECTION → NOT_SIGNED_UP` transitions added.

---

## Migration Checklist

Before running the bot after this feature:

- [ ] Migration `009_module_system.sql` applied (automatic on `run_migrations()` startup).
- [ ] `divisions` table recreated with `forecast_channel_id INTEGER` (nullable).
- [ ] `server_configs` has `weather_module_enabled` and `signup_module_enabled` columns.
- [ ] All existing `server_configs` rows have both columns defaulting to `0` (disabled).

---

## Access Control Summary

| Command | Tier | Decorators |
|---------|------|-----------|
| `/module enable|disable` | Server admin | `@channel_guard @admin_only` |
| `/signup config *` | Server admin | `@channel_guard @admin_only` |
| `/signup nationality|time-type|time-image toggle` | Server admin | `@channel_guard @admin_only` |
| `/signup time-slot add|remove|list` | Server admin | `@channel_guard @admin_only` |
| `/signup enable|disable` | Server admin | `@channel_guard @admin_only` |

---

## Testing Approach

Unit tests for `ModuleService`:
- Enable weather: happy path, division missing forecast channel, module already enabled.
- Disable weather: happy path, cancels jobs, module already disabled.
- Enable signup: happy path, config missing, bot lacks channel permissions.
- Disable signup: happy path, signups open (force-close path), module already disabled.

Unit tests for `SignupModuleService`:
- Slot add: happy path, duplicate, max slots, signups open guard.
- Slot remove: happy path, invalid ID, signups open guard.
- Signup open: happy path, no slots, already open.
- Signup close: happy path, already closed, button message not found (graceful).

Integration tests (if applicable):
- Migration `009` applies cleanly to a database that already has migrations `001–008`.
- Existing division rows survive the `divisions` table recreation with `NULL`-capable column.
