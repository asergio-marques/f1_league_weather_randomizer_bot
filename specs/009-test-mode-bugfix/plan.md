# Implementation Plan: Test Mode Bug Fixes

**Branch**: `009-test-mode-bugfix` | **Date**: 2026-03-05 | **Spec**: [spec.md](spec.md)
**Input**: Bug reports from live test-mode usage; fixes to existing feature `002-test-mode`.

**Reuses plan**: See [`specs/001-league-weather-bot/plan.md`](../001-league-weather-bot/plan.md)
for the full tech stack, structural decisions, and base data model. Everything in that plan
applies unchanged. Only the files listed in the Scope table below require edits.

## Summary

Six bugs in the `002-test-mode` implementation are corrected.

Bugs 1–3 were identified and fixed first; Bugs 4–6 were discovered during live usage
and fixed in the same branch session.

1. **Mystery round "next round" leak** — `/season-status` cited Mystery rounds as pending
   next rounds. Fix: exclude `MYSTERY` from the `next_round` predicate in `season_cog`.

2. **Season stuck ACTIVE after advance exhausts queue** — Returning `None` from the phase
   queue without checking for a live season left the season permanently stuck. Fix: safety
   net calls `execute_season_end` when queue is empty and season still exists.

3. **Test-mode commands required admin** — Missing `guild_only` and `default_permissions`
   on the Group let Discord fall back to cached `manage_guild` restrictions. Fix: set
   `guild_only=True, default_permissions=None` so `channel_guard` is the sole gate.

4. **Mystery notice never fires in test mode** — APScheduler (`mystery_r{id}`) never runs
   in test mode; the notice was silently skipped. Fix: `get_next_pending_phase` returns a
   `phase_number=0` sentinel for unnoticed Mystery rounds; the cog dispatches
   `run_mystery_notice` and marks `phase1_done=1` on success.

5. **Reset raises FK violation when forecast_messages exists** — `reset_service` skipped
   deleting `forecast_messages` before `rounds`, violating the FK. Fix: add the delete in
   the correct position in the FK-safe chain.

6. **Advance logs show DB id instead of round number** — Log lines emitted `rounds.id`
   (meaningless to managers). Fix: add `round_number` to `PhaseEntry` and emit both
   `round=<round_number>` and `id=<round_id>` in the log line.

## Technical Context

**Language/Version**: Python 3.13.2 (targets 3.8+)
**Primary Dependencies**: discord.py 2.7.1, aiosqlite ≥ 0.19, APScheduler ≥ 3.10
**Storage**: SQLite via aiosqlite — no schema changes
**Testing**: pytest 9.0.2 + pytest-asyncio (`asyncio_mode = auto`); `pythonpath = src`
**Target Platform**: Any host running Python 3.8+ with a Discord bot token
**Project Type**: Discord bot (event-driven, async)
**Performance Goals**: No new hot paths introduced
**Constraints**: No new slash commands; no schema migrations; no new dependencies
**Scale/Scope**: Five source files modified; two test files updated; no new files created

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked post-implementation.*

| Principle | Requirement | Status |
|-----------|-------------|--------|
| I — Trusted Configuration Authority | Bug 3 fix restores correct Tier-1 enforcement: interaction-role check in `channel_guard` gates all three `/test-mode` subcommands; no admin-only escalation | ✅ PASS |
| II — Multi-Division Isolation | No cross-division logic touched | ✅ PASS |
| III — Resilient Schedule Management | Season-end safety net follows existing `execute_season_end` atomicity; no partial-update path introduced. Mystery notice dispatch mirrors the scheduler path; `phase1_done` is set only after a successful send | ✅ PASS |
| IV — Three-Phase Weather Pipeline | Mystery round exclusion aligns with the spec: Mystery rounds must never have phases executed or reported as pending. Mystery notice is a pre-pipeline signal, not a phase | ✅ PASS |
| V — Observability & Change Audit Trail | Season-end safety net posts the existing completion message to the log channel. Advance log lines now include user-visible round number alongside DB id for triage | ✅ PASS |
| VI — Simplicity & Focused Scope | All changes are minimal targeted corrections; no scope expansion | ✅ PASS |
| VII — Output Channel Discipline | No new output channels used; season-end posts to the configured log channel only | ✅ PASS |

**Constitution Check result: PASS — no violations, no Complexity Tracking entries required.**

## Research Notes

*No Phase 0 required* — All fixes are scoped to existing code paths and patterns already
established in `002-test-mode`. Key design decisions:

- **Bug 4 (mystery notice proxy)**: Reuse `rounds.phase1_done = 1` as the "notice sent"
  marker rather than adding a new column. Safe because `all_phases_complete` and
  `build_review_summary` already filter `format != 'MYSTERY'`, so the flag has no
  side-effects on season-end or review logic. No migration needed.

- **Bug 4 (phase_number=0 sentinel)**: Using `0` as the mystery-notice sentinel in
  `PhaseEntry` cleanly separates it from real phases (1/2/3) without introducing a new
  enum or TypedDict variant. The cog dispatch is a simple `if phase_number == 0` guard
  before the existing `phase_runners` dict.

- **Bug 5 (FK deletion order)**: SQLite FK enforcement is ON via `PRAGMA foreign_keys = ON`
  on every connection. The correct deletion chain for this schema is:
  `sessions → phase_results → forecast_messages → rounds → divisions → seasons`.

## Scope

| File | Change |
|------|--------|
| `src/cogs/season_cog.py` | Add `r.format != RoundFormat.MYSTERY` guard to `next_round` generator in `season_status` |
| `src/cogs/test_mode_cog.py` | Season-end safety net; `guild_only=True` + `default_permissions=None`; `phase_number=0` mystery-notice dispatch; log lines use `round_number` |
| `src/services/test_mode_service.py` | Add `round_number` to `PhaseEntry`; widen `get_next_pending_phase` to include Mystery rounds; return `phase_number=0` sentinel |
| `src/services/reset_service.py` | Add `DELETE FROM forecast_messages` after `phase_results`, before `rounds` |
| `tests/unit/test_test_mode_service.py` | Rename + rewrite mystery exclusion test; add `test_mystery_round_notice_done_excluded` |
| `tests/unit/test_reset_service.py` | Add `test_reset_deletes_forecast_messages` regression test |
| `.specify/memory/constitution.md` | Add Sync Impact Report entry documenting all six bugs and fixes |

## Project Structure

### Documentation (this feature)

```text
specs/009-test-mode-bugfix/
├── plan.md    ← this file
├── spec.md    ← bug specifications (covers all 6 bugs)
└── tasks.md   ← task list (T001–T012 + quality gates)
```

No `research.md`, `data-model.md`, `quickstart.md`, or `contracts/` — this is a
targeted bug-fix with no new data model, no new API surface, and no research phase.

### Source Code edits

```text
src/
├── cogs/
│   ├── season_cog.py             ← Bug 1 fix (next_round mystery exclusion)
│   └── test_mode_cog.py          ← Bug 2+3 fix (safety net, permissions)
│                                    + Bug 4 fix (mystery notice dispatch)
│                                    + Bug 6 fix (round_number in logs)
├── services/
│   ├── test_mode_service.py      ← Bug 4 fix (PhaseEntry.round_number + phase_number=0)
│   └── reset_service.py          ← Bug 5 fix (forecast_messages delete)
tests/
└── unit/
    ├── test_test_mode_service.py  ← Updated tests for Bug 4
    └── test_reset_service.py      ← Regression test for Bug 5
.specify/
└── memory/
    └── constitution.md            ← Sync Impact Report entry
```
