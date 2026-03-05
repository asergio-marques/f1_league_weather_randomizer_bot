---

description: "Task list for test mode bug fixes (branch 009-test-mode-bugfix)"
---

# Tasks: Test Mode Bug Fixes

**Input**: Design documents from `specs/009-test-mode-bugfix/`
**Prerequisites**: plan.md ✅ spec.md ✅

**Status**: All tasks complete — implementation committed on `009-test-mode-bugfix` (covers all 6 bugs).

**Organization**: Tasks are grouped by user story (one bug per story) to enable
independent review and verification.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no unmet dependencies)
- **[Story]**: Which user story / bug this task addresses (US1–US3)
- No story label on Setup and Polish phase tasks

---

## Phase 1: Setup

**Purpose**: Create the feature specification directory and documents so the branch
has full SpecKit traceability.

- [X] T001 Create `specs/009-test-mode-bugfix/` with `plan.md` and `spec.md`

**Checkpoint**: Feature directory present — bug-fix tasks can begin.

---

## Phase 2: Foundational (Blocking Prerequisites)

**N/A** — No new infrastructure, no migrations, no new files required. All fixes are
targeted edits to two existing source files. Bug-fix phases may proceed immediately.

---

## Phase 3: User Story 1 — Mystery Rounds Must Not Appear as "Next Round" (P1) 🎯

**Goal**: `/season-status` reports "None remaining" for any division whose only
incomplete rounds are Mystery rounds. Non-Mystery rounds are still surfaced correctly.

**Independent Test**: Seed a season with one fully-phased Normal round and one Mystery
round; run `/season-status`; verify the bot reports "None remaining" for that division.

- [X] T002 [P] [US1] Add `r.format != RoundFormat.MYSTERY` guard to the `next_round`
  generator expression inside `season_status` in `src/cogs/season_cog.py`

**Checkpoint**: Bug 1 resolved — `/season-status` no longer cites Mystery rounds as pending.

---

## Phase 4: User Story 2 — Season Ends Correctly When Advance Queue Is Exhausted (P2)

**Goal**: When `/test-mode advance` is called after all non-Mystery phases are done,
the Season is ended immediately if it is still `ACTIVE` (safety net), or the user
receives a "nothing to advance" message if the season is already cleared.

**Independent Test**: Enable test mode; advance all phases; call advance one more time;
verify the season is cleared and `/season-status` reports "No active season found."

- [X] T003 [US2] Replace the bare `followup.send` early-return (when `entry is None`) in
  the `advance` command with a safety-net block that calls `get_active_season` — if a
  season is still live, cancel the pending scheduled job and call `execute_season_end`
  before responding; otherwise send the existing "nothing to advance" message — in
  `src/cogs/test_mode_cog.py`

**Checkpoint**: Bug 2 resolved — season cannot remain stuck `ACTIVE` after test-mode
advance exhausts all phases.

---

## Phase 5: User Story 3 — Test-Mode Commands Respect the Configured Interaction Role (P2)

**Goal**: All three `/test-mode` subcommands are accessible to holders of the configured
interaction role (set via `/bot-init`) and rejected for users without it — regardless of
admin/Manage Server permissions. The commands do not appear in DMs.

**Independent Test**: After adding fixes and re-syncing the command tree, verify that a
non-admin user with the interaction role can issue `/test-mode toggle` successfully, and
that an admin without the role is rejected by `channel_guard`.

- [X] T004 [US3] Add `guild_only=True` and `default_permissions=None` to the
  `test_mode = app_commands.Group(...)` class attribute in `src/cogs/test_mode_cog.py`
  so Discord resets any cached platform-level restriction on the next tree sync and
  `channel_guard` remains the sole enforcement gate

**Checkpoint**: Bug 3 resolved — Discord no longer applies admin-level restrictions to
`/test-mode` commands; a fresh `/tree sync` propagates the corrected permissions.

---

## Phase 6: User Story 4 — Mystery Round Notice Dispatched via Test-Mode Advance (P1)

**Goal**: `/test-mode advance` detects Mystery rounds with unsent notices, fires them,
and marks the round as noticed. Subsequent calls skip noticed rounds.

- [X] T007 [US4] Add `round_number: int` to `PhaseEntry`; widen `get_next_pending_phase`
  query in `src/services/test_mode_service.py` to include all rounds; return
  `phase_number=0` for unnoticed Mystery rounds (`phase1_done=0`); skip noticed ones
- [X] T008 [US4] Add `phase_number == 0` dispatch block in `src/cogs/test_mode_cog.py`
  advance command: call `run_mystery_notice`, set `phase1_done=1` on success, reply with
  notice-sent ephemeral; on failure reply with error ephemeral without setting the flag
- [X] T009 [US4] Update `tests/unit/test_test_mode_service.py`: rename
  `test_mystery_rounds_excluded` to `test_mystery_round_notice_pending_returns_entry`
  (assert `phase_number==0`); add `test_mystery_round_notice_done_excluded`

**Checkpoint**: Bug 4 resolved — Mystery notices fire during test-mode advance.

---

## Phase 7: User Story 5 — Reset Clears `forecast_messages` Without FK Violation (P1)

**Goal**: `/bot-reset` completes on any server that has Phase 1 data.

- [X] T010 [US5] Add `DELETE FROM forecast_messages WHERE round_id IN ({ph})` after
  `phase_results` delete and before `rounds` delete in `src/services/reset_service.py`
- [X] T011 [US5] Add `test_reset_deletes_forecast_messages` regression test in
  `tests/unit/test_reset_service.py`

**Checkpoint**: Bug 5 resolved — reset transaction never raises FK constraint failed.

---

## Phase 8: User Story 6 — Advance Logs Show User-Visible Round Number (P3)

**Goal**: Log lines include `round=<round_number>` and `id=<round_id>` for all dispatch
paths.

- [X] T012 [US6] Update log line in `src/cogs/test_mode_cog.py` advance command to emit
  `round=<entry["round_number"]>` alongside `id=<entry["round_id"]>` for both mystery
  and normal phase paths

**Checkpoint**: Bug 6 resolved — logs are unambiguous to league managers.

---

## Final Phase: Quality Gates

**Purpose**: Confirm all fixes are consistent with the constitution and that the full
test suite remains green.

- [X] T005 [P] Add Sync Impact Report entry to `.specify/memory/constitution.md`
  documenting all six bugs, their root causes, fixes, and which principles each
  correction restores
- [X] T006 [P] Run `pytest tests/ -q` and verify all 164 tests pass with no regressions

**Checkpoint**: Branch ready for PR.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: N/A — skipped.
- **Bug Fixes (Phases 3–8)**: All depend only on Setup. Phases 3–8 target different
  files or non-overlapping sections; they may be worked in parallel with care:
  - T002 (`season_cog.py`) — fully independent.
  - T003/T004/T008/T012 are all in `test_mode_cog.py` — apply sequentially.
  - T007 (`test_mode_service.py`) — independent of cog changes.
  - T010 (`reset_service.py`) — independent.
  - T009/T011 (test files) — apply after their corresponding service/cog changes.
- **Quality Gates (Final Phase)**: Depend on all bug-fix phases being complete.

### User Story Dependencies

- **US1 (T002)**: Independent.
- **US2 (T003)**: Independent; same file as T004/T008/T012 — apply sequentially.
- **US3 (T004)**: Independent; same file as T003/T008/T012 — apply sequentially.
- **US4 (T007, T008, T009)**: T008 depends on T007 (needs `phase_number=0` in entry).
- **US5 (T010, T011)**: T011 depends on T010.
- **US6 (T012)**: Depends on T007 (`round_number` field in `PhaseEntry`).
- **Quality Gates (T005, T006)**: Depend on all T002–T012 being complete.

---

## Parallel Execution Examples

```text
# Independent across files:
Task T002: next_round guard in season_cog.py
Task T007: PhaseEntry + get_next_pending_phase in test_mode_service.py
Task T010: forecast_messages delete in reset_service.py

# Sequential within test_mode_cog.py:
T004 (Group attrs) → T003 (advance safety net) → T008 (mystery dispatch) → T012 (log line)

# Tests after their service/cog:
T009 after T007 | T011 after T010

# Quality gates last:
T005 + T006 in parallel once all bug tasks done
```

---

## Implementation Strategy

Recommended order for sequential work:

1. **T001** — create feature docs.
2. **T002** — season_cog next_round fix (simplest).
3. **T004** — test_mode_cog Group attribute fix.
4. **T003** — test_mode_cog advance safety net.
5. **T007** — test_mode_service PhaseEntry + widened query.
6. **T008** — test_mode_cog mystery-notice dispatch.
7. **T012** — test_mode_cog log line update.
8. **T010** — reset_service forecast_messages delete.
9. **T009, T011** — test updates.
10. **T005 + T006** — constitution sync and test verification.

Each fix can be independently validated before moving to the next.
