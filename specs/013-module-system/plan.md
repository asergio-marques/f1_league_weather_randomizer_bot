# Implementation Plan: Module System — Weather & Signup Modules

**Branch**: `013-module-system` | **Date**: 2026-03-07 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/013-module-system/spec.md`

## Summary

Introduce a per-server module enable/disable system so that the weather pipeline and the
signup pipeline are default-off capabilities that admins activate explicitly. Weather module
state is stored as boolean columns on `server_configs`; enabling it arms all overdue and
future weather phase jobs via `SchedulerService`. The signup module stores its own
configuration in two new tables (`signup_module_config`, `signup_module_settings`) and a
time-slots table; enabling it applies Discord channel permission overwrites. Both modules are
toggled via a new `/module` command group, and signup window management is exposed via a new
`/signup` command group. The `Division.forecast_channel_id` field becomes nullable, gated by
weather module state. Two new driver state transitions (`PENDING_SIGNUP_COMPLETION → NOT_SIGNED_UP`,
`PENDING_DRIVER_CORRECTION → NOT_SIGNED_UP`) are added to `DriverService` to support forced
signup close on module disable.

**Technologies**: unchanged from project baseline — Python 3.13.2, discord.py 2.7.1,
APScheduler 3.11.2, aiosqlite 0.22.1, SQLite, pytest + pytest-asyncio.

## Technical Context

**Language/Version**: Python 3.13.2  
**Primary Dependencies**: discord.py 2.7.1, APScheduler 3.11.2 (AsyncIOScheduler + SQLAlchemyJobStore), aiosqlite 0.22.1, sqlalchemy (job store only), python-dotenv  
**Storage**: SQLite via aiosqlite; raw SQL; file-based migrations applied on startup via `run_migrations()`  
**Testing**: pytest + pytest-asyncio  
**Target Platform**: Discord bot (guild/server scope) — always-on async service  
**Project Type**: Discord bot / event-driven service  
**Performance Goals**: Interaction acknowledgment within 3 s (Discord limit); phase catch-up completes within the deferred followup window (~15 min maximum, practically < 1 s per phase)  
**Constraints**: Single SQLite file; no ORM; bot must remain recoverable across restarts (APScheduler persists jobs in SQLite job store)  
**Scale/Scope**: Single guild per deployment; < 10 divisions per season; < 25 time slots

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Status |
|-----------|-------------|--------|
| I — Access Control | All commands use `@channel_guard` + `@admin_only`; module/settings commands require `MANAGE_GUILD`; slot/open/close require interaction role | ✅ PASS |
| II — Audit Trail | `MODULE_ENABLE`, `MODULE_DISABLE`, `SIGNUP_OPEN`, `SIGNUP_CLOSE`, `SIGNUP_FORCE_CLOSE` audit entries emitted | ✅ PASS |
| III — Simplicity | No new abstractions beyond two services and two cogs; no ORM; no repository layer | ✅ PASS |
| IV — Correctness First | Phase catch-up is sequential and synchronous; failures revert module flag; no silent partial state | ✅ PASS |
| V — Reversibility | Module disable is fully reversible; config cleared on disable (per spec); no data loss on re-enable (slots and settings are created fresh) | ✅ PASS |
| VI — Incremental Scope | This plan covers module infrastructure and signup module shell only; signup wizard deferred to feature 014 | ✅ PASS |
| VII — Module-Channel Discipline | Signup module has a dedicated channel; weather module uses per-division `forecast_channel`; no channel overloading | ✅ PASS |
| VIII — Database Integrity | Foreign keys declared; `ON DELETE CASCADE` on all new module tables referencing `server_configs`; migration recreates `divisions` table to allow NULL | ✅ PASS |
| IX — Recovery | Scheduler recovery in `on_ready` (`_recover_missed_phases`) gated by `weather_module_enabled` check after this feature | ✅ PASS |
| X — Modular Feature Architecture | Weather and signup are implemented as independent, encapsulated modules behind a single `ModuleService` toggle; exactly the pattern Principle X mandates | ✅ PASS |

**Post-design re-check**: All gates still pass. No `divisions` table recreation causes any FK
orphan because the recreated table preserves all rows and all FKs intact.

## Project Structure

### Documentation (this feature)

```text
specs/013-module-system/
├── plan.md              ← This file
├── research.md          ← Phase 0 output (produced)
├── data-model.md        ← Phase 1 output (produced)
├── quickstart.md        ← Phase 1 output (produced)
├── contracts/
│   ├── module.md        ← /module enable|disable contracts
│   ├── signup.md        ← /signup group contracts
│   └── division-changes.md  ← forecast_channel conditionality changes
└── tasks.md             ← Phase 2 output (/speckit.tasks — NOT produced here)
```

### Source Code (repository root)

```text
src/
├── cogs/
│   ├── module_cog.py          ← NEW: /module enable|disable weather|signup
│   └── signup_cog.py          ← NEW: /signup config, nationality/time-type/time-image toggles,
│                                        time-slot add/remove/list, enable, disable
├── models/
│   ├── division.py            ← MODIFY: forecast_channel_id: int → int | None
│   ├── server_config.py       ← MODIFY: add weather_module_enabled, signup_module_enabled fields
│   └── signup_module.py       ← NEW: SignupModuleConfig, SignupModuleSettings, AvailabilitySlot
├── services/
│   ├── module_service.py      ← NEW: is_enabled(), enable_weather(), disable_weather(),
│   │                                   enable_signup(), disable_signup()
│   ├── signup_module_service.py ← NEW: get/save config+settings, slot CRUD, open/close window
│   ├── scheduler_service.py   ← MODIFY: cancel_all_weather_for_server(); gate schedule_round()
│   ├── driver_service.py      ← MODIFY: add two new state transitions (FR-037)
│   └── phase1_service.py      ← MODIFY (minor): guard already gated via scheduler; no change
│                                   unless direct call paths exist outside scheduler
└── db/
    └── migrations/
        └── 009_module_system.sql  ← NEW

tests/
├── unit/
│   ├── test_module_service.py       ← NEW
│   └── test_signup_module_service.py ← NEW
└── integration/
    └── (existing integration test fixtures may need migration updates)
```

**Structure Decision**: Single project, existing layout. Two new cogs, two new services,
one new model file, two modified models, one new migration, two new test files. No new
directories are added.

## Complexity Tracking

No constitution violations. All additions stay within existing project conventions.
