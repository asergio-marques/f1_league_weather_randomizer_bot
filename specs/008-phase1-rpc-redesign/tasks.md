---
description: "Task list for Phase 1 Rpc Distribution Redesign"
---

# Tasks: Phase 1 Rpc Distribution Redesign

**Input**: Design documents from `specs/008-phase1-rpc-redesign/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md)
**Branch**: `008-phase1-rpc-redesign`

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story this task belongs to (US1 / US2 / US3)
- Exact file paths included in every task description

---

## Phase 1: Setup

**Purpose**: No new project scaffolding is needed — the repository already exists. This phase establishes the one structural artefact required before any other work can proceed.

- [X] T001 Create migration file `src/db/migrations/005_track_rpc_params.sql` — `CREATE TABLE IF NOT EXISTS track_rpc_params (track_name TEXT PRIMARY KEY, mu_rain_pct REAL NOT NULL, sigma_rain_pct REAL NOT NULL, updated_at TEXT NOT NULL, updated_by TEXT NOT NULL)`

**Checkpoint**: Migration file exists and will be picked up automatically by `database.py run_migrations()` on next startup.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core in-code changes that are prerequisites for all three user stories. US1 cannot draw from Beta without `compute_rpc_beta`. US2 and US3 cannot resolve effective parameters without `TRACK_DEFAULTS` and `get_effective_rpc_params`. Both tasks touch different files and can proceed in parallel after T001.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Update `src/models/track.py` — replace `TRACKS: dict[str, float]` with `TRACK_DEFAULTS: dict[str, tuple[float, float]]` (all 27 tracks with μ and σ from Default Parameter Table in spec.md); replace `get_btrack` with `get_default_rpc_params(name) -> tuple[float, float]`; add `get_effective_rpc_params(name, override_mu, override_sigma) -> tuple[float, float]` (returns server override if both non-None, else packaged default; raises `ValueError` if track has no packaged default)
- [X] T003 [P] Update `src/utils/math_utils.py` — replace `compute_rpc(btrack, rand1, rand2)` with `compute_rpc_beta(mu: float, sigma: float) -> tuple[float, float]` returning `(raw_draw, rpc)` where: `ν = μ(1−μ)/σ²−1`, `α = μν`, `β_param = (1−μ)ν`, draw via `random.betavariate(α, β_param)`, clamp to [0.0, 1.0], round `rpc` to 2 decimal places; raise `ValueError` for invalid α/β (infeasible σ); keep old `compute_rpc` as a deprecated stub that raises `DeprecationWarning` so existing callers surface clearly

**Checkpoint**: Foundation ready — `TRACK_DEFAULTS` resolves for all 27 circuits; `compute_rpc_beta` produces a valid `(raw_draw, rpc)` tuple; user story implementation can now begin.

---

## Phase 3: User Story 1 — Draw Rpc from Beta Distribution (Priority: P1) 🎯 MVP

**Goal**: At T−5d Phase 1 trigger, `Rpc` is drawn from the per-track Beta distribution and the correct audit payload and forecast message are produced; the old `(Btrack * rand1 * rand2) / 3.025` formula is gone.

**Independent Test**: Trigger Phase 1 for a single round against a seeded test environment; assert `Rpc ∈ [0.0, 1.0]`, confirm calc-log payload contains `distribution`, `mu`, `sigma`, `alpha`, `beta_param`, `raw_draw`, `rpc`, and forecast message is posted.

### Tests for User Story 1

- [X] T004 [P] [US1] Update `tests/unit/test_math_utils.py` — replace all `compute_rpc` tests with `compute_rpc_beta` tests covering: normal mid-range draw (μ=0.30, σ=0.05), low-μ track (μ=0.05, σ=0.02), boundary clamp (manually verified: raw draw forced outside [0,1] via monkeypatching `random.betavariate`), infeasible σ raises `ValueError` (σ ≥ √(μ(1−μ))), return type is `tuple[float, float]`, `rpc` rounded to 2dp

### Implementation for User Story 1

- [X] T005 [US1] Update `src/services/phase1_service.py` — (a) query `track_rpc_params` for server override row; (b) call `track_model.get_effective_rpc_params(track_name, override_mu, override_sigma)` — if this raises `ValueError` (track unknown, no packaged default), post FR-015 error to calc-log channel and return without posting forecast message; (c) call `compute_rpc_beta(mu, sigma)` — if this raises `ValueError` (infeasible σ), log the error to calc-log channel and return; (d) replace old `{btrack, rand1, rand2, rpc}` calc-log payload with expanded payload: `{"phase": 1, "round_id": ..., "track": ..., "distribution": "beta", "mu": ..., "sigma": ..., "alpha": ..., "beta_param": ..., "raw_draw": ..., "rpc": ...}`; (e) public forecast message format unchanged: `"Weather radar information for @<DivisionRole>: the likelihood of rain in the next round in <Track> is <Rpc>%!"`

**Checkpoint**: Phase 1 draws from Beta, posts correct message, logs complete Beta audit payload. The old formula is fully removed. US1 independently testable.

---

## Phase 4: User Story 2 — Admin Configures Per-Track Parameters (Priority: P1)

**Goal**: Config-authority users can update μ and σ for any track via `/track config` and query current effective values via `/track info`; every successful write produces a timestamped audit entry.

**Independent Test**: Issue `/track config track:Belgium mu:0.30 sigma:0.08`; assert DB row written to `track_rpc_params`; assert ephemeral confirmation returned; assert audit entry recorded; issue with bad σ (≤ 0) and assert rejection before any write.

### Tests for User Story 2

- [X] T006 [P] [US2] Create `tests/unit/test_track_service.py` — unit tests covering: `set_track_override` persists row and returns old values for audit; `set_track_override` rejects μ ≤ 0.0, μ ≥ 1.0, σ ≤ 0.0 with `ValueError` before writing; `get_track_override` returns `None` when no row exists; audit entry is written on successful `set_track_override`

### Implementation for User Story 2

- [X] T007 [US2] Create `src/services/track_service.py` — implement: `get_track_override(db, track_name) -> tuple[float, float] | None` (SELECT from `track_rpc_params`); `set_track_override(db, track_name, mu, sigma, actor) -> None` — validate μ ∈ (0.0, 1.0) exclusive and σ > 0.0 (raise `ValueError` with descriptive message on failure), UPSERT row into `track_rpc_params`, write audit entry (actor, track, old values, new values, UTC timestamp) via existing audit mechanism; `reset_track_override` stub (placeholder, full impl in T010)
- [X] T008 [US2] Create `src/cogs/track_cog.py` — `TrackCog(commands.Cog)` with `@app_commands.group(name="track")`; `/track config track sigma mu` — decorated `@admin_only @channel_guard`, calls `track_service.set_track_override`, returns ephemeral confirmation or descriptive error; `/track info track` — decorated `@channel_guard`, calls `get_track_override` + `get_default_rpc_params`, returns ephemeral embed showing effective μ, σ, source (override / default), and (if override) when it was set and by whom
- [X] T009 [US2] Register `TrackCog` in `src/bot.py` — add `await bot.add_cog(TrackCog(bot))` alongside existing cog registrations

**Checkpoint**: `/track config` and `/track info` fully functional; validation and audit trail working. US2 independently testable.

---

## Phase 5: User Story 3 — Default Parameter Values Ship with Bot + Reset Command (Priority: P2)

**Goal**: A fresh database with no admin overrides works out of the box for all 27 circuits; admins can revert any override to the packaged default via `/track reset`.

**Independent Test**: Run Phase 1 on a freshly initialised database for any circuit from the Default Parameter Table; assert the packaged default μ/σ were used (no DB override row). Then issue `/track reset track:Belgium`; assert override row is deleted from `track_rpc_params`, audit entry recorded, subsequent Phase 1 draw for Belgium uses packaged default.

### Implementation for User Story 3

- [X] T010 [P] [US3] Complete `reset_track_override` in `src/services/track_service.py` — implement: DELETE row from `track_rpc_params` for the given track (no-op if row does not exist); write audit entry (actor, track, old values, "reset to default", UTC timestamp); return old `(mu, sigma)` if a row existed, else `None`
- [X] T011 [US3] Add `/track reset` subcommand to `src/cogs/track_cog.py` — decorated `@admin_only @channel_guard`; calls `track_service.reset_track_override`; if no override existed returns ephemeral "no override set, already using defaults"; otherwise returns ephemeral confirmation showing the old override that was cleared

**Checkpoint**: All three user stories independently functional. Clean-database deployment works out of the box for all 27 tracks. US3 independently testable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Cleanup of import references across unchanged-business-logic cogs, and the README documentation mandated by FR-014.

- [X] T012 [P] Update import in `src/cogs/season_cog.py` — change `from models.track import TRACKS, TRACK_IDS` to `from models.track import TRACK_DEFAULTS, TRACK_IDS`; update all `if name in TRACKS` validity checks to `if name in TRACK_DEFAULTS`
- [X] T013 [P] Update import in `src/cogs/amendment_cog.py` — change `from models.track import TRACKS` to `from models.track import TRACK_DEFAULTS`; update validity check to `if name in TRACK_DEFAULTS`
- [X] T014 Add "Track Distribution Parameters" section to `README.md` — document: how μ (mean rain probability) and σ (dispersion) parameterise the Beta distribution; how increasing σ widens the distribution and pushes probability into the tails; the J-shaped / humped-bell transition that occurs when α = μν crosses 1 (with concrete numeric examples for Bahrain μ=0.05 and United Kingdom μ=0.30); guidance on choosing σ (bigger σ → more surprising draws)
- [X] T015 Run full test suite (`pytest`) and validate key flows against `quickstart.md` — confirm: all unit tests pass, Phase 1 draws from Beta and logs the expanded payload, `/track config` accepts valid inputs and rejects invalid, `/track reset` clears overrides and is reflected in the next Phase 1 draw

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 → Phase 2**: T001 MUST complete before T002/T003 (schema file must exist before code references it)
- **Phase 2 → Phase 3**: T002 and T003 MUST complete before Phase 3 (US1 calls both)
- **Phase 2 → Phase 4**: T002 MUST complete before Phase 4 (US2 resolves effective params)
- **Phase 3 → Phase 5**: T005 MUST complete before Phase 5 validation (FR-015 path uses `get_effective_rpc_params`)
- **Phase 4 → Phase 5**: T007 MUST complete before T010 (T010 extends track_service); T008 MUST complete before T011 (T011 extends track_cog)
- **Phase 5 → Phase 6**: All US phases SHOULD complete before Polish

### User Story Dependencies

- **US1 (P1)**: Foundation (Phase 2) complete — no dependency on US2 or US3
- **US2 (P1)**: Foundation (Phase 2) complete — no dependency on US1 (independently testable)
- **US3 (P2)**: Foundation (Phase 2) complete — extends US2 artefacts (track_service, track_cog) but independently testable via clean-DB scenario

### Parallel Opportunities

Within Phase 2: T002 and T003 target different files — run in parallel.

Within Phase 3: T004 (tests) and foundation are both ready — T004 can be written before T005.

Within Phase 4: T006 (tests) can be written before T007 (implementation) — write-fail-implement TDD if desired. T007 and T008 target different files — once T007 is done, T008 can proceed independently of T009.

Within Phase 6: T012 and T013 touch different files — run in parallel alongside T014.

---

## Parallel Example: Phase 2

```text
# Both can start immediately after T001:
Task T002: Update src/models/track.py  (TRACK_DEFAULTS, get_default_rpc_params, get_effective_rpc_params)
Task T003: Update src/utils/math_utils.py  (compute_rpc_beta)
```

## Parallel Example: Phase 4

```text
# T006 can proceed alongside T007 (different files):
Task T006: Create tests/unit/test_track_service.py
Task T007: Create src/services/track_service.py

# After T007 completes, T008 and the bot registration proceed:
Task T008: Create src/cogs/track_cog.py
Task T009: Update src/bot.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only — Core Mechanical Change)

1. Complete Phase 1: T001 — migration file
2. Complete Phase 2: T002 + T003 — foundation (parallel)
3. Complete Phase 3: T004 + T005 — Beta draw live in Phase 1
4. **STOP and VALIDATE**: `pytest tests/unit/test_math_utils.py`, trigger Phase 1 manually via test environment, confirm Beta payload in calc-log
5. Deploy if ready (US2/US3 can follow for admin configuration surface)

### Incremental Delivery

1. Phase 1 + Phase 2 → Foundation ready
2. Phase 3 → US1 (core formula live) → MVP
3. Phase 4 → US2 (admin commands) → `/track config` and `/track info` available
4. Phase 5 → US3 (defaults + reset) → full out-of-the-box experience
5. Phase 6 → Polish (imports, README)

---

## Summary

| Phase | Tasks | User Story | Notes |
|-------|-------|------------|-------|
| Phase 1 — Setup | T001 | — | Migration file |
| Phase 2 — Foundational | T002, T003 | — | Blocks all US; run T002/T003 in parallel |
| Phase 3 — US1 | T004, T005 | US1 (P1) | Core Beta draw; MVP complete here |
| Phase 4 — US2 | T006, T007, T008, T009 | US2 (P1) | Admin config commands |
| Phase 5 — US3 | T010, T011 | US3 (P2) | Reset command + defaults |
| Phase 6 — Polish | T012, T013, T014, T015 | — | Imports, README, validation |

**Total tasks**: 15  
**Parallel opportunities**: T002/T003 (Phase 2); T006/T007 (Phase 4); T012/T013 (Phase 6)  
**Suggested MVP scope**: Phases 1–3 (T001–T005, 5 tasks, delivers US1 end-to-end)
