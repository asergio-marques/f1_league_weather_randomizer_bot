# Task Plan: 003 — Track ID Autocomplete & Division Command Cleanup

**Branch**: `003-track-id-autocomplete`  
**Created**: 2026-03-04  
**Status**: Complete  
**Source**: [plan.md](plan.md)

---

## Execution Rules

- Phases must be completed in order (Setup → Tests → Core → Integration → Polish).
- Tasks marked **[P]** within a phase may be executed in parallel.
- Tasks that touch the same file must be executed sequentially.
- Mark each task **[X]** as soon as it is done.

---

## Phase 1 — Setup

### T001 — Fix bot startup crash (`bot_init` rename) [P]
- **File**: `src/cogs/init_cog.py`
- **Action**: Rename method `bot_init` → `handle_bot_init`. The `@app_commands.command(name="bot-init")` decorator preserves the Discord-facing command name.
- **Why first**: The bot cannot start until this is resolved; all other work depends on a running bot.
- **Status**: [X]

### T002 — Add `TRACK_IDS` registry [P]
- **File**: `src/models/track.py`
- **Action**: Add `TRACK_IDS: Final[dict[str, str]]` constant — 27 circuits keyed `"01"`–`"27"` in alphabetical order by canonical name.
- **Status**: [X]

### T003 — Write DB migration 003 [P]
- **File**: `src/db/migrations/003_remove_division_race_fields.sql`
- **Action**: `ALTER TABLE divisions DROP COLUMN race_day;` and `ALTER TABLE divisions DROP COLUMN race_time;`
- **Status**: [X]

---

## Phase 2 — Core: Data model & service layer

### T004 — Remove `race_day`/`race_time` from `Division` model
- **File**: `src/models/division.py`
- **Action**: Delete `race_day: int` and `race_time: str` fields from the `Division` dataclass.
- **Depends on**: T003
- **Status**: [X]

### T005 — Remove `race_day`/`race_time` from `SeasonService`
- **File**: `src/services/season_service.py`
- **Action**: Remove parameters from `add_division()` signature; update INSERT, SELECT, and `_row_to_division` helper.
- **Depends on**: T004
- **Status**: [X]

---

## Phase 3 — Core: Discord command layer

### T006 — Update `/division-add` command [P]
- **File**: `src/cogs/season_cog.py`
- **Action**: Remove `race_day` and `race_time` from `PendingDivision`, `@app_commands.describe`, the function signature, validation block, and confirmation message. Update `_do_approve` call to `add_division()`.
- **Depends on**: T005
- **Status**: [X]

### T007 — Add track autocomplete to `/round-add` [P]
- **File**: `src/cogs/season_cog.py`
- **Action**: Import `TRACK_IDS`. Update `@app_commands.describe` for `track`. Add ID → name resolution before validation. Register `@round_add.autocomplete("track")` callback that filters `TRACK_IDS` entries by `current` (case-insensitive substring, max 25 results).
- **Depends on**: T002
- **Status**: [X]

### T008 — Add track autocomplete to `/round-amend` [P]
- **File**: `src/cogs/amendment_cog.py`
- **Action**: Import `TRACK_IDS`. Update `@app_commands.describe` for `track`. Add ID → name resolution before validation. Register `@round_amend.autocomplete("track")` callback identical to T007's.
- **Depends on**: T002
- **Status**: [X]

### T009 — Update `/season-review` division display
- **File**: `src/cogs/season_cog.py`
- **Action**: Remove `day_names[div.race_day]` and `div.race_time` from the review summary string in `season_review()`.
- **Depends on**: T006
- **Status**: [X]

---

## Phase 4 — Documentation & Polish

### T010 — Update README with per-command parameter tables [P]
- **File**: `README.md`
- **Action**: Replace the sparse commands table with per-command sections each containing a parameter table (name, type, required, description). Add track ID quick-reference table.
- **Status**: [X]

### T011 — Update test seed fixtures [P]
- **File**: `tests/unit/test_test_mode_service.py`
- **Action**: Remove `race_day` and `race_time` columns from all division `INSERT` statements in the `_seed()` helper.
- **Depends on**: T003
- **Status**: [X]

---

## Phase 5 — Validation

### T012 — Run full test suite
- **Action**: `python -m pytest tests/ -v` — all 45 tests must pass.
- **Depends on**: T001–T011
- **Status**: [X]

### T013 — Verify bot startup
- **Action**: `python src/bot.py` — must log "All cogs loaded. Starting bot..." without `TypeError`.
- **Depends on**: T001–T011
- **Status**: [X]

---

## Summary

| Phase | Tasks | Status |
|-------|-------|--------|
| 1 — Setup | T001, T002, T003 | ✅ Complete |
| 2 — Data model & service | T004, T005 | ✅ Complete |
| 3 — Command layer | T006, T007, T008, T009 | ✅ Complete |
| 4 — Documentation & polish | T010, T011 | ✅ Complete |
| 5 — Validation | T012, T013 | ✅ Complete |

**All 13 tasks complete. 45/45 tests passing.**
