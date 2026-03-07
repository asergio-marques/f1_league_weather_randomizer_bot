# Implementation Plan: Driver Profiles, Teams & Season Enhancements

**Branch**: `012-driver-profiles-teams` | **Date**: 2026-03-06 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/012-driver-profiles-teams/spec.md`

## Summary

Introduce two new persisted data structures (DriverProfile with state machine, and team
management via DefaultTeam / TeamInstance / TeamSeat) plus targeted enhancements to the
existing season/division model (season counter, division tier, tier-sequential approval gate,
expanded season review output).

New Discord commands are strictly limited to those marked `<NEW COMMAND>` in the source
specification: `/driver reassign` (User ID swap), `/test-mode set-former-driver` (flag
override), `/team default` (server default team CRUD), and `/team season` (season-scoped team
CRUD during SETUP). All other changes extend existing command behaviour or add background
enforcement logic.

Implementation approach: additive SQLite migrations for the new tables and columns, new model
dataclasses, new service classes (`DriverService`, `TeamService`) following the existing
service pattern, and a new `DriverCog` plus extensions to `SeasonCog` and `TestModeCog`.

## Technical Context

**Language/Version**: Python 3.8+ (3.12 recommended); already in use — no change  
**Primary Dependencies**: discord.py ≥ 2.0, aiosqlite ≥ 0.19, APScheduler ≥ 3.10,
python-dotenv — all already in `requirements.txt`; no new packages required  
**Storage**: SQLite via aiosqlite; async connection managed by `src/db/database.py`;
migrations applied automatically on startup from `src/db/migrations/`  
**Testing**: pytest + pytest-asyncio; existing suite in `tests/unit/` and `tests/integration/`  
**Target Platform**: Linux server (or any platform running the bot process); no change  
**Project Type**: Discord bot (event-driven async Python application)  
**Performance Goals**: All bot commands must acknowledge within 3 seconds (Constitution
Bot Behavior Standards). New DB access patterns are single-row lookups or short
range-scans — no bulk aggregations. SQLite at current scale (~tens to low hundreds of
drivers per server) is sufficient per constitution performance analysis.  
**Constraints**: No new Python packages. All mutations transactional and reversible. FK
constraints enforced (PRAGMA foreign_keys = ON already in `get_connection`). New commands
must use the `/domain action` subcommand-group convention (Constitution Bot Behavior
Standards) — existing `test-mode` group is grandfathered pending migration.  
**Scale/Scope**: Per-server. New table row counts are O(drivers) for profiles,
O(teams × divisions × seasons) for seats — both small. No indexes beyond those already
specified in the data model are needed at this scale.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I** — Two-tier access (interaction role / admin role) | ✅ PASS | All four new commands use `@admin_only` via the existing `channel_guard` decorator. State-machine transitions triggered by driver-facing flows will also gate on interaction role. No implicit super-user. |
| **II** — Multi-division isolation | ✅ PASS | TeamInstance and TeamSeat are keyed by (division_id). DriverProfile is server-scoped (not division-scoped) per spec, which is correct — a driver may participate in multiple divisions. Division-level season data joins through the division FK. |
| **III** — Resilient schedule management | ✅ PASS | No changes to the round/schedule pipeline. |
| **IV** — Three-phase weather pipeline | ✅ PASS | No changes to phase execution or Mystery round handling. |
| **V** — Observability & change audit trail | ✅ PASS | All four new commands and every state-machine transition MUST append to `audit_entries`. User ID reassignment, `former_driver` flag overrides, and team mutations are all covered in FR-008, FR-009, and the audit trail. |
| **VI** — Incremental scope expansion | ✅ PASS | Driver profiles, teams, and season enhancements are all formally in-scope domains as of Constitution v2.0.0. |
| **VII** — Output channel discipline | ✅ PASS | All new command responses are ephemeral. No new public channels are introduced. Season review is an existing ephemeral admin command. |
| **VIII** — Driver profile integrity | ✅ PASS | State machine, former_driver immutability, deletion rule, User ID reassignment, and test-mode overrides are all directly specified in FR-001–FR-011. |
| **IX** — Team & division structural integrity | ✅ PASS | Reserve invariant, 2-seat default, division isolation, sequential tier gate, and tier uniqueness are all directly specified in FR-012–FR-025. |

**Post-Phase-1 re-check**: All gates remain green after data-model and contract design —
see `data-model.md` and `contracts/` for detailed entity and command schemas.

## Project Structure

### Documentation (this feature)

```text
specs/012-driver-profiles-teams/
├── plan.md         # This file
├── research.md     # Phase 0 output
├── data-model.md   # Phase 1 output
├── quickstart.md   # Phase 1 output
├── contracts/      # Phase 1 output
│   └── commands.md
└── tasks.md        # Phase 2 output (created by /speckit.tasks, not this command)
```

### Source Code (repository root)

```text
src/
├── cogs/
│   ├── season_cog.py           # MODIFIED — division add/duplicate gain tier param;
│   │                           #   season approve gains tier-sequential gate;
│   │                           #   season review output extended with team rosters
│   ├── test_mode_cog.py        # MODIFIED — new /test-mode set-former-driver subcommand
│   └── driver_cog.py           # NEW — /driver reassign
│
├── db/
│   └── migrations/
│       └── 008_driver_profiles_teams.sql  # NEW — all new tables + column additions
│
├── models/
│   ├── division.py             # MODIFIED — add tier: int field
│   ├── season.py               # MODIFIED — add season_number: int field
│   ├── server_config.py        # MODIFIED — add previous_season_number: int field
│   ├── driver_profile.py       # NEW — DriverProfile dataclass + DriverState enum
│   └── team.py                 # NEW — DefaultTeam, TeamInstance, TeamSeat dataclasses
│
├── services/
│   ├── season_service.py       # MODIFIED — season number logic; division tier;
│   │                           #   tier validation on approve; team auto-creation;
│   │                           #   expanded review query
│   ├── driver_service.py       # NEW — DriverService (state machine, CRUD, reassign)
│   └── team_service.py         # NEW — TeamService (default CRUD, season CRUD)
│
└── utils/
    └── message_builder.py      # MODIFIED — season review roster formatting

tests/
├── unit/
│   ├── test_driver_service.py          # NEW — state machine + deletion rule
│   ├── test_team_service.py            # NEW — Reserve invariant, default/season CRUD
│   └── test_season_tier_validation.py  # NEW — tier sequential gate
└── integration/
    └── test_driver_profiles_teams.py   # NEW — end-to-end across service/DB
```

**Structure Decision**: Single project layout (existing `src/` root). No new top-level
directories. Follows the established pattern of one model file per entity group, one
service class per domain, one cog per command group.

## Complexity Tracking

> No Constitution violations. Table is empty — all design choices comply with Principles I–IX.
