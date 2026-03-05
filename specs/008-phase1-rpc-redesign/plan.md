# Implementation Plan: Phase 1 Rpc Distribution Redesign

**Branch**: `008-phase1-rpc-redesign` | **Date**: 2026-03-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/008-phase1-rpc-redesign/spec.md`

**Reuses plan**: See [`specs/001-league-weather-bot/plan.md`](../001-league-weather-bot/plan.md)
for the full tech stack, structural decisions, and base data model. Everything in that plan
applies unchanged. Only the files listed in the Scope table below require edits or creation.

## Summary

Replace the Phase 1 `Rpc` calculation (`(Btrack * rand1 * rand2) / 3025`) with a stochastic
draw from a **Beta distribution** parameterised by a per-track mean (`μ`) and dispersion
(`σ`). Both parameters have **bot-packaged immutable defaults** for all 27 known circuits; a
config-authority user may store **server-level overrides** for any track via `/track config`
and revert them to packaged defaults via `/track reset`. Phase 1 resolves effective
parameters at draw time (server override → packaged default). All downstream phases are
unchanged; `Rpc` remains a float in [0.0, 1.0].

**Technical approach**: `random.betavariate(α, β)` from the Python stdlib is used for
sampling — no new dependencies. α and β are derived from μ and σ at call time:
`ν = μ(1−μ)/σ²−1`, `α = μν`, `β = (1−μ)ν`. `math_utils.compute_rpc` is replaced by
`compute_rpc_beta(mu, sigma) → (raw_draw, rpc)`. `track.py` replaces `TRACKS: dict[str, float]`
with `TRACK_DEFAULTS: dict[str, tuple[float, float]]` (name → (μ, σ)) and replaces `get_btrack`
with `get_default_rpc_params`. A new `track_rpc_params` DB table stores nullable server
overrides resolved at runtime. A new `TrackCog` exposes `/track config` and `/track reset`.
Phase 1 payload is expanded with Beta-specific audit fields; the public message format is
unchanged.

## Technical Context

**Language/Version**: Python 3.13.2 (targets 3.8+)
**Primary Dependencies**: discord.py 2.7.1, aiosqlite ≥ 0.19, APScheduler ≥ 3.10 — no new
  dependencies; `random.betavariate` is part of Python stdlib
**Storage**: SQLite via aiosqlite — one new migration (`005_track_rpc_params.sql`)
**Testing**: pytest 9.0.2 + pytest-asyncio (`asyncio_mode = auto`); `pythonpath = src`
**Target Platform**: Any host running Python 3.8+ with a Discord bot token
**Project Type**: Discord bot (event-driven, async)
**Performance Goals**: Beta sampling is O(1); no meaningful performance impact on Phase 1
**Constraints**: No changes to Phase 2 or Phase 3 contracts; public Phase 1 message format
  unchanged; `random.betavariate` only; no scipy/numpy
**Scale/Scope**: 27 tracks × 1 override row each (max); bounded constant-size DB addition

## Constitution Check

*GATE — evaluated before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Status |
|-----------|-------------|--------|
| I — Trusted Configuration Authority | `/track config` and `/track reset` are gated by `@admin_only` + `@channel_guard`; only config-authority tier can change distribution parameters | ✅ PASS |
| II — Multi-Division Isolation | Track parameters are global per-track (server-wide); Phase 1 draws are performed independently per division as before; no cross-division state | ✅ PASS |
| III — Resilient Schedule Management | Amendment invalidation path unchanged; newly drawn `Rpc` (after amendment) uses same Beta logic; no re-draw on parameter config change | ✅ PASS |
| IV — Three-Phase Weather Pipeline | Phase 1 replaces only the `Rpc` production step; T−5d trigger, Phase 2/3 contracts, Mystery Round skip, and amendment-invalidation semantics are all unchanged | ✅ PASS |
| V — Observability & Change Audit Trail | Phase 1 calc-log payload is expanded with μ, σ, α, β, raw draw, distribution type. `/track config` and `/track reset` write audit entries per FR-007 | ✅ PASS |
| VI — Simplicity & Focused Scope | Change is surgical: new Beta sampling replaces one formula call; one new slash command group; one new migration. No expansion of bot scope | ✅ PASS |
| VII — Output Channel Discipline | No new channel categories. Phase 1 public message posted to division forecast channel; audit entries posted to calc-log channel. Config command responses are ephemeral | ✅ PASS |

**Constitution Check result: PASS — no violations, no Complexity Tracking entries required.**

*Re-check post-design*: All principles confirmed. No violations introduced by Phase 1 data model (nullable override columns + new table).

## Scope

| File | Change |
|------|--------|
| `src/db/migrations/005_track_rpc_params.sql` | **New** — `track_rpc_params` table (server override rows, nullable → falls back to packaged defaults) |
| `src/models/track.py` | Replace `TRACKS: dict[str, float]` with `TRACK_DEFAULTS: dict[str, tuple[float,float]]`; replace `get_btrack` with `get_default_rpc_params`; add `get_effective_rpc_params` |
| `src/utils/math_utils.py` | Replace `compute_rpc(btrack, rand1, rand2)` with `compute_rpc_beta(mu, sigma) → tuple[float, float]`; retain old function as deprecated no-op shim until tests are updated |
| `src/services/phase1_service.py` | Load effective (μ, σ) via `track_service`; call `compute_rpc_beta`; expand payload with Beta audit fields; handle "no params" block + calc-log error (FR-015) |
| `src/services/track_service.py` | **New** — `get_track_override`, `set_track_override`, `reset_track_override`; all write audit entries |
| `src/cogs/track_cog.py` | **New** — `/track config`, `/track reset`, `/track info`; all `@admin_only @channel_guard` |
| `src/cogs/season_cog.py` | Update `TRACKS` import → `TRACK_DEFAULTS`; update validity check (`if name in TRACK_DEFAULTS`) |
| `src/cogs/amendment_cog.py` | Update `TRACKS` import → `TRACK_DEFAULTS` |
| `src/bot.py` | Register `TrackCog` |
| `README.md` | Add "Track Distribution Parameters" section documenting Beta shape, μ/σ chaos knob, J-shape transition (FR-014) |
| `tests/unit/test_math_utils.py` | Replace `compute_rpc` tests with `compute_rpc_beta` tests; add boundary tests (μ→0, μ→1, large σ) |
| `tests/unit/test_track_service.py` | **New** — unit tests for override CRUD + audit entries |

## Project Structure

### Documentation (this feature)

```text
specs/008-phase1-rpc-redesign/
├── plan.md          ← this file
├── spec.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md         ← generated by /speckit.tasks
```

### Source Code (repository root)

```text
src/
├── cogs/
│   ├── track_cog.py         ← NEW
│   └── season_cog.py        ← updated (TRACKS → TRACK_DEFAULTS import)
│   └── amendment_cog.py     ← updated (TRACKS → TRACK_DEFAULTS import)
├── models/
│   └── track.py             ← updated (TRACKS → TRACK_DEFAULTS, get_btrack → get_default_rpc_params)
├── services/
│   ├── track_service.py     ← NEW
│   └── phase1_service.py    ← updated (Beta draw, expanded payload, FR-015 guard)
├── utils/
│   └── math_utils.py        ← updated (compute_rpc_beta replaces compute_rpc)
├── db/
│   └── migrations/
│       └── 005_track_rpc_params.sql  ← NEW
└── bot.py                   ← updated (register TrackCog)

tests/
└── unit/
    ├── test_math_utils.py       ← updated
    └── test_track_service.py    ← NEW
```

**Structure Decision**: Single-project layout (existing); all changes within `src/` and
`tests/unit/`. No new top-level directories.
