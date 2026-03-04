# Implementation Plan: F1 League Weather Randomizer Bot — Core System

**Branch**: `001-league-weather-bot` | **Date**: 2026-03-03 | **Spec**: [specs/001-league-weather-bot/spec.md](spec.md)  
**Input**: Feature specification from `specs/001-league-weather-bot/spec.md`

## Summary

A Discord bot for F1 league racing servers that automates weather randomization across
multiple divisions. A trusted admin configures the season interactively (divisions, tracks,
round formats, schedules). The bot then runs three autonomous phases per non-Mystery round at
fixed horizons (T−5 days, T−2 days, T−2 hours), posting weather forecasts to per-division
channels and computation records to a central log channel. Mid-season amendments are handled
with atomic invalidation and phase re-execution.

**Technical approach**: Python asyncio Discord bot using discord.py for Discord interaction,
APScheduler for exact-horizon phase triggers, and SQLite via aiosqlite for durable
persistence of all season data and phase results.

## Technical Context

**Language/Version**: Python 3.8+ (Python 3.12 installed)  
**Primary Dependencies**:
- `discord.py` (installed) — Discord bot framework, slash commands, ephemeral messages, deferred responses
- `APScheduler` ≥ 3.10 — persistent job scheduler for exact-datetime phase triggers; avoids polling loops
- `aiosqlite` — async SQLite driver; keeps storage self-contained with no external server

**Storage**: SQLite (single file, co-located with bot); versioned schema with applied-at-startup migrations  
**Testing**: `pytest` + `pytest-asyncio`  
**Target Platform**: Always-on Linux/Windows server process (no web-facing surface)  
**Project Type**: Discord bot (long-running async process)  
**Performance Goals**: Phase messages delivered within 5 minutes of horizon; bot acknowledges all commands within 3 seconds  
**Constraints**: Text-only output in this revision; image generation deferred to a future spec amendment  
**Scale/Scope**: Single Discord server per bot instance; up to ~10 divisions; up to ~25 rounds per division per season

### Additional Dependencies to Install

The following are not yet installed and will be required:

| Package | Version | Purpose |
|---------|---------|---------|
| `APScheduler` | ≥ 3.10 | Exact-time phase scheduling |
| `aiosqlite` | ≥ 0.19 | Async SQLite persistence |
| `pytest` | ≥ 7 | Test runner |
| `pytest-asyncio` | ≥ 0.23 | Async test support |

Install with: `pip install apscheduler aiosqlite pytest pytest-asyncio`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Gate | Status | Notes |
|-----------|------|--------|-------|
| I — Trusted Configuration Authority | Two-tier access (interaction role + config authority) enforced everywhere; out-of-channel commands silently ignored | ✅ | `channel_guard` utility applied to every command handler; both tiers stored in Server Config entity |
| II — Multi-Division Isolation | Division is a first-class scoped entity; all queries and scheduler jobs are keyed by `(server_id, division_id)` | ✅ | No cross-division reads anywhere in data layer |
| III — Resilient Schedule Management | Amendment service atomically updates round, reschedules APScheduler jobs, and triggers invalidation flow | ✅ | APScheduler job identity keyed by `(round_id, phase_num)`; replace-on-amend |
| IV — Three-Phase Weather Pipeline | APScheduler `DateTrigger` jobs created at season approval for each phase of each non-Mystery round; Mystery rounds never get jobs | ✅ | Pipeline is enforced structurally — phases cannot be manually invoked, only triggered by scheduler |
| V — Observability & Change Audit Trail | Every phase logs to log channel; every config mutation records actor, division, change type, old/new value, timestamp | ✅ | `PhaseResult` entity carries full input/output snapshot; `AuditEntry` entity for mutations |
| VI — Simplicity & Focused Scope | Bot exposes only: init, season, division, round amendment, and passthrough query commands; no standings, results, or penalties | ✅ | Text-only output confirmed for this revision |
| VII — Output Channel Discipline | `channel_guard` and `OutputRouter` enforce that only the two registered channel types ever receive messages | ✅ | Any channel write outside the two categories raises a logged error, never silently succeeds |

**Constitution Check result: PASS — no violations, no Complexity Tracking entries required.**

## Project Structure

### Documentation (this feature)

```text
specs/001-league-weather-bot/
├── plan.md              # This file
├── checklists/
│   └── requirements.md  # Spec quality checklist (complete)
└── tasks.md             # Created by /speckit.tasks — not yet created
```

### Source Code (repository root)

```text
src/
├── bot.py                      # Entry point: creates Bot, loads cogs, starts APScheduler
├── models/
│   ├── __init__.py
│   ├── server_config.py        # ServerConfig: interaction role, interaction channel, log channel
│   ├── season.py               # Season: start date, lifecycle state (SETUP/ACTIVE/COMPLETED)
│   ├── division.py             # Division: id, mention role, forecast channel, race day/time
│   ├── round.py                # Round: number, format, track, scheduled datetime, phase status flags
│   ├── session.py              # Session: type, Phase 2 draw, Phase 3 slot sequence
│   ├── phase_result.py         # PhaseResult: phase number, inputs, outputs, ACTIVE/INVALIDATED
│   ├── audit_entry.py          # AuditEntry: actor, division, change type, old/new values, timestamp
│   └── track.py                # Track: name, Btrack base factor (27 entries, read-only)
├── db/
│   ├── __init__.py
│   ├── database.py             # aiosqlite connection pool, migration runner
│   └── migrations/
│       └── 001_initial.sql     # Full schema: all tables + indexes
├── services/
│   ├── __init__.py
│   ├── config_service.py       # Bot init, ServerConfig CRUD, role/channel validation
│   ├── season_service.py       # Season CRUD, lifecycle transitions, division/round management
│   ├── scheduler_service.py    # APScheduler setup; create/replace/cancel phase jobs per round
│   ├── phase1_service.py       # Phase 1 computation (Rpc formula, Btrack lookup, log, post)
│   ├── phase2_service.py       # Phase 2 computation (1000-slot map, session draws, log, post)
│   ├── phase3_service.py       # Phase 3 computation (Nslots draw, weighted maps, log, post)
│   ├── amendment_service.py    # Atomic amendment: update round, invalidate phases, re-schedule
│   └── output_router.py        # OutputRouter: enforces channel discipline (Principle VII)
├── cogs/
│   ├── __init__.py
│   ├── init_cog.py             # /bot init — server initialisation (server admin only)
│   ├── season_cog.py           # /season setup, /season approve, /season review, /season status
│   └── amendment_cog.py        # /round amend — track/date/format changes (trusted admin only)
└── utils/
    ├── __init__.py
    ├── channel_guard.py        # Decorator: enforce interaction channel + role on every command
    ├── message_builder.py      # All Discord message string templates (Phase 1/2/3, invalidation)
    └── math_utils.py           # Rpc formula, slot-count maps, Phase 2/3 weight formulas, clamping

tests/
├── conftest.py                 # Shared fixtures: in-memory SQLite DB, mock Discord client
├── unit/
│   ├── test_phase1.py          # Rpc formula correctness, Btrack lookups, boundary rand values
│   ├── test_phase2.py          # Slot-map construction, draw distribution, edge sum ≠ 1000 case
│   ├── test_phase3.py          # Nslots bounds, weight formulas, clamping to 0, mixed-all-wet case
│   ├── test_amendment.py       # Invalidation state transitions, re-schedule logic
│   └── test_message_builder.py # Message string correctness for each format and edge case
└── integration/
    └── test_scheduler.py       # Scheduler fires correct phase at correct horizon; restart recovery
```

**Structure Decision**: Single-project layout. The bot has no web frontend and no separate
API surface; all logic lives under `src/`. Cogs separate Discord command handling from
business logic services, which keeps services independently testable without a real Discord
client. `output_router.py` is the single chokepoint for all channel writes — every service
calls it rather than writing to Discord directly — enforcing Principle VII structurally.

## Phase 0 Research Notes

### discord.py Slash Commands and Interaction Model
- `discord.ext.commands.Bot` with `app_commands` for slash commands; `Cog` subclasses group
  related commands.
- Ephemeral responses: `interaction.response.send_message(..., ephemeral=True)`.
- Deferred responses for long operations: `await interaction.response.defer(ephemeral=True)`,
  then `await interaction.followup.send(...)`.
- Interactive configuration sessions (multi-step): use a `discord.ui.View` with buttons or
  a sequential prompt loop keyed by `interaction.user.id` and stored in bot state.
- Role checks: `discord.utils.get(interaction.guild.roles, id=role_id)` and membership test
  via `role in interaction.user.roles`.

### APScheduler Phase Scheduling
- `AsyncIOScheduler` from APScheduler 3.x integrates with `asyncio` event loop.
- `DateTrigger(run_date=datetime)` fires exactly once at the specified UTC datetime —
  correct for per-round phase triggers.
- Jobs are identified by a string `id`; use `f"phase{n}_r{round_id}"` to allow
  replace-on-amend (`replace_existing=True`) without creating duplicates.
- For restart recovery: use APScheduler's `SQLAlchemyJobStore` backed by the same SQLite
  database so scheduled jobs survive process restarts. Jobs whose `run_date` has already
  passed are fired immediately on scheduler start — this satisfies the missed-phase recovery
  requirement from spec edge case 2.

### SQLite Schema Considerations
- All timestamps stored as `TEXT` in ISO 8601 UTC format for human readability in the log.
- `phase_results` table has a `status` column (`ACTIVE` | `INVALIDATED`) and a `payload`
  column (`TEXT` / JSON blob) storing the complete input/output snapshot for auditability.
- Foreign key constraints enabled via `PRAGMA foreign_keys = ON` on every connection.
- Migration runner: on startup, read applied migration IDs from a `schema_migrations` table
  and execute any unapplied `.sql` files in order.

### Weather Formula Notes
- **Phase 2 `Ir` formula** — corrected formula confirmed by spec author:
  `Ir = floor((1000 × Rpc × (1 + Rpc)²) / 5)`. No algebraic resolution needed; this is
  a direct, non-self-referential computation and MUST be used in `phase2_service.py`.
- **Phase 3 Overcast/mixed formula** — confirmed by spec author as:
  `40 + (30 × Prain) - (70 × Prain^1.7)`. No ambiguity remains.
- All weight values MUST be clamped to `max(0, value)` before being used as map entry counts.
  If all weights clamp to zero the map is empty; this edge case MUST raise a logged error and
  default to an equal-weight fallback across all valid weather types for that session type,
  never crash the phase.

## Data Model Summary

See full schema in `db/migrations/001_initial.sql` (to be authored in Phase 1).

| Table | Key columns |
|-------|-------------|
| `server_configs` | `server_id` PK, `interaction_role_id`, `interaction_channel_id`, `log_channel_id` |
| `seasons` | `id` PK, `server_id` FK, `start_date`, `status` (SETUP/ACTIVE/COMPLETED) |
| `divisions` | `id` PK, `season_id` FK, `name`, `mention_role_id`, `forecast_channel_id`, `race_day`, `race_time` |
| `rounds` | `id` PK, `division_id` FK, `round_number`, `format`, `track_name`, `scheduled_at`, `phase1_done`, `phase2_done`, `phase3_done` |
| `sessions` | `id` PK, `round_id` FK, `session_type`, `phase2_slot_type`, `phase3_slots` (JSON) |
| `phase_results` | `id` PK, `round_id` FK, `phase_number`, `payload` (JSON), `status`, `created_at` |
| `audit_entries` | `id` PK, `server_id`, `actor_id`, `actor_name`, `division_id`, `change_type`, `old_value`, `new_value`, `timestamp` |
| `schema_migrations` | `id` PK, `applied_at` |

