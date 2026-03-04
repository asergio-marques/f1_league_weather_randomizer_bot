# Implementation Plan: Track ID Autocomplete & Division Command Cleanup

**Branch**: `003-track-id-autocomplete` | **Date**: 2026-03-04 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/003-track-id-autocomplete/spec.md`

## Summary

Remove the redundant `race_day`/`race_time` parameters from `/division-add` (each round already carries its own `scheduled_at`), add a Discord autocomplete dropdown to the `track` parameter of `/round-add` and `/round-amend` using a numeric ID → canonical name mapping, fix a bot startup crash caused by a `bot_`-prefixed method name in `InitCog`, and expand the README with per-command parameter tables.

## Technical Context

**Language/Version**: Python 3.13.2 (targets 3.8+)  
**Primary Dependencies**: discord.py 2.7.1 (`app_commands.Choice`, `@command.autocomplete`), aiosqlite ≥ 0.19, APScheduler ≥ 3.10  
**Storage**: SQLite via aiosqlite; schema versioned with sequential SQL migration files applied on startup  
**Testing**: pytest 9.0.2 + pytest-asyncio (`asyncio_mode = auto`)  
**Target Platform**: Windows/Linux server running Python 3.8+  
**Project Type**: Discord bot (slash commands)  
**Performance Goals**: Command acknowledgement within 3 seconds (Discord hard limit); autocomplete callback ≤ 200 ms  
**Constraints**: Autocomplete limited to 25 choices per Discord API; track registry has 27 entries — handled with substring filtering  
**Scale/Scope**: Single-server bot; changes affect the season configuration flow only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Trusted Configuration Authority | ✅ PASS | `/division-add`, `/round-add`, `/round-amend` remain behind `@admin_only` + `@channel_guard`. No access-tier changes. |
| II — Multi-Division Isolation | ✅ PASS | Division data model change (removing `race_day`/`race_time`) is an additive database migration; per-division isolation is unaffected. |
| III — Resilient Schedule Management | ✅ PASS | `/round-amend` gains autocomplete but its amendment logic (atomic DB update, scheduler re-arm) is unchanged. |
| IV — Three-Phase Weather Pipeline | ✅ PASS | No changes to phase services or scheduling horizons. |
| V — Observability & Change Audit Trail | ✅ PASS | No audit-log or log-channel changes. |
| VI — Simplicity & Focused Scope | ✅ PASS | Changes reduce surface area (fewer params on `/division-add`) and improve UX without adding new commands. |
| VII — Output Channel Discipline | ✅ PASS | No new output channels or message types introduced. |

**Post-Phase 1 re-check**: No violations identified in design or implementation.

## Project Structure

### Documentation (this feature)

```text
specs/003-track-id-autocomplete/
├── plan.md          ← this file
├── research.md      ← Phase 0
├── data-model.md    ← Phase 1
├── quickstart.md    ← Phase 1
└── tasks.md         ← Phase 2 (/speckit.task)
```

### Source Code changes

```text
src/
├── models/
│   ├── division.py          # removed race_day / race_time fields
│   └── track.py             # added TRACK_IDS mapping
├── services/
│   └── season_service.py    # removed race_day/race_time from add_division + SELECT
├── cogs/
│   ├── season_cog.py        # removed params from division_add; added track autocomplete to round_add
│   ├── amendment_cog.py     # added track autocomplete to round_amend
│   └── init_cog.py          # renamed bot_init → handle_bot_init (startup crash fix)
└── db/migrations/
    └── 003_remove_division_race_fields.sql  # DROP COLUMN race_day, race_time

tests/
└── unit/
    └── test_test_mode_service.py  # updated seed INSERT statements
```

**Structure Decision**: Single-project layout (`src/` + `tests/`), consistent with features 001 and 002.

## Complexity Tracking

> No Constitution violations — table omitted.

