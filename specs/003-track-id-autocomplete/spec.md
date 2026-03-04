# Feature Specification: Track ID Autocomplete & Division Command Cleanup

**Feature Branch**: `003-track-id-autocomplete`  
**Created**: 2026-03-04  
**Status**: Draft  
**Input**: User description: "Remove race_day and race_time from division-add command, add numeric track ID autocomplete to round-add and round-amend, and document all command parameters in README"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Division setup no longer asks for race day/time (Priority: P1)

An admin configuring a new season runs `/division-add`. Currently the command asks for `race_day` (0–6 integer) and `race_time` (HH:MM string). These inputs are confusing because the round's date and time are already provided via `/round-add`'s `scheduled_at` parameter — duplicating them on the division level is redundant and error-prone.

**Why this priority**: Directly reduces setup friction and removes a source of inconsistency in the data model. Affects every new season configuration.

**Independent Test**: Run `/division-add` with only `name`, `role`, and `forecast_channel`. The division must be created successfully and the pending config must reflect only those three fields.

**Acceptance Scenarios**:

1. **Given** a pending season setup, **When** `/division-add` is called with `name`, `role`, and `forecast_channel`, **Then** the division is accepted without `race_day` or `race_time` and the success message shows only the division name and channel.
2. **Given** a pending season setup, **When** `/division-add` is called with extra `race_day`/`race_time` arguments, **Then** Discord rejects the command at the slash-command parameter level (parameters no longer exist in the schema).
3. **Given** an approved season, **When** the database is inspected, **Then** the `divisions` table contains no `race_day` or `race_time` columns.

---

### User Story 2 — Track selection via ID autocomplete dropdown (Priority: P1)

An admin adding a round with `/round-add` must type the exact track name (e.g., `"United Kingdom"`). Typos silently produce an error after Discord sends the command. Discord's autocomplete mechanism can present a filtered pick-list instead, guiding the user to a valid value before submission.

**Why this priority**: Eliminates the largest source of input errors during season configuration. Track names with spaces or ambiguous spellings (e.g., `"Texas"` vs `"Austin"`) are typo-prone.

**Independent Test**: Use `/round-add` and start typing a number or partial name in the `track` field. A dropdown of `ID – Name` choices must appear and filtering must work. Selecting one must populate the `track` field with the canonical track name.

**Acceptance Scenarios**:

1. **Given** a `/round-add` command is being filled, **When** the user types a number (e.g., `"27"`) in the `track` field, **Then** the autocomplete shows `27 – United Kingdom` as a matching option.
2. **Given** a `/round-add` command is being filled, **When** the user types a partial name (e.g., `"bah"`), **Then** the autocomplete shows `05 – Bahrain`.
3. **Given** a `/round-add` command is submitted with a valid autocomplete selection, **Then** the round is created with the correct canonical track name stored in the database.
4. **Given** a `/round-amend` command is being filled, **When** the user types in the `track` field, **Then** the same autocomplete dropdown appears and behaves identically.
5. **Given** a `/round-add` command is submitted with a bare numeric ID (e.g., `"5"`), **Then** the bot resolves it to the canonical name and creates the round successfully (fallback for manual input).

---

### User Story 3 — README documents all command parameters (Priority: P2)

A new server admin reads the README to understand how to set up the bot. The current README lists commands in a sparse table with no detail about accepted parameters. They cannot configure a season without referring to the source code.

**Why this priority**: Documentation is additive value that does not affect runtime behaviour and can be deferred if needed; the command changes above are more critical.

**Independent Test**: A reader with no prior knowledge of the bot can, using only the README, successfully understand which parameters to pass to each command and what each does.

**Acceptance Scenarios**:

1. **Given** a reader on the README, **When** they look up `/division-add`, **Then** they see every parameter, its type, whether it is required, and a description.
2. **Given** a reader on the README, **When** they look up `/round-add`, **Then** the `track` parameter entry explains the ID autocomplete and links to the track ID table.
3. **Given** a reader on the README, **When** they look up the track ID table, **Then** all 27 circuit IDs are listed with their canonical names.

---

### Edge Cases

- What happens when a user types a track ID that does not correspond to any circuit (e.g., `"99"`)? → The ID lookup returns no match; the canonical-name validation then catches it and returns a descriptive error.
- What happens when autocomplete returns a value but the bot's track registry has drifted? → The canonical name is re-validated server-side on submission; it cannot be bypassed via autocomplete.
- What happens to existing `bot.db` databases that still have `race_day`/`race_time` columns in `divisions`? → Migration 003 drops those columns; it runs automatically on next bot startup.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `/division-add` command MUST NOT include `race_day` or `race_time` parameters.
- **FR-002**: The `divisions` table MUST NOT contain `race_day` or `race_time` columns after migration 003 is applied.
- **FR-003**: The `track` parameter of `/round-add` MUST offer a Discord autocomplete dropdown showing all 27 circuits as `ID – Name` entries.
- **FR-004**: The `track` parameter of `/round-amend` MUST offer the same Discord autocomplete dropdown.
- **FR-005**: Autocomplete results MUST be filtered in real time to entries whose `ID – Name` label contains the user's current input (case-insensitive substring match).
- **FR-006**: Both `/round-add` and `/round-amend` MUST resolve a bare numeric ID (e.g., `"5"` or `"05"`) to its canonical track name before validation when the user types manually without using the dropdown.
- **FR-007**: Track validation MUST remain server-side; a track value that does not resolve to a known circuit MUST be rejected with a descriptive error.
- **FR-008**: The README MUST document every slash command with a parameter table listing name, type, required/optional, and description.
- **FR-009**: The README MUST include a track ID quick-reference table listing all 27 circuit IDs.
- **FR-010**: The bot startup error caused by `cog_`/`bot_`-prefixed method names MUST be resolved (rename `bot_init` → `handle_bot_init`).

### Key Entities

- **TRACK_IDS**: An ordered mapping of zero-padded two-digit string IDs (`"01"`–`"27"`) to canonical track names. Defined in `src/models/track.py` alongside existing `TRACKS`.
- **PendingDivision**: In-memory dataclass used during season setup. Removes `race_day` and `race_time` fields.
- **Division** (DB model): Removes `race_day: int` and `race_time: str` fields.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `/division-add` accepts exactly three user-supplied parameters (`name`, `role`, `forecast_channel`) — no more, no fewer.
- **SC-002**: Typing any digit 1–27 in the `/round-add` or `/round-amend` `track` field returns at least one autocomplete suggestion.
- **SC-003**: Typing a partial track name (minimum 2 characters) in the `track` field returns at least one matching autocomplete suggestion.
- **SC-004**: All existing tests continue to pass after the migration and model changes.
- **SC-005**: The README contains a parameter table for every slash command.
- **SC-006**: The bot starts without errors (`python src/bot.py` exits cleanly and logs "All cogs loaded").

---

## Addendum — Bot Data Reset Command (2026-03-04)

### Clarifications

- Q: Scope of the reset — entire file or server-scoped? → A: Server-scoped only; only rows belonging to the invoking server are deleted. Other guilds sharing the same `bot.db` are unaffected.
- Q: What gets deleted — seasons only or include server config? → A: Both modes; a `full` boolean parameter selects between partial (seasons + dependents only, server config preserved) and full (everything including server config).
- Q: Confirmation UX? → A: `confirm: str` parameter; the user must type `CONFIRM` exactly before any data is deleted.

---

### User Story 4 — Server admin resets all bot data for their server (Priority: P1)

A server administrator needs to wipe all bot data for their Discord server — e.g., after a test run or before starting a new league season from scratch. They should not need SSH or direct filesystem access.

**Why this priority**: Required for the system-testing use case (the `rm bot.db` attempt in the terminal proves it). Without this, admins must delete the file manually, which wipes all other servers.

**Independent Test**: Run `/bot-reset confirm:CONFIRM full:False` on a server with an active season. All seasons, divisions, rounds, sessions, phase results, and audit entries for that server MUST be deleted; the server config row MUST remain; all APScheduler jobs for those rounds MUST be cancelled.

**Acceptance Scenarios**:

1. **Given** a server with an active season and config, **When** `/bot-reset confirm:CONFIRM full:False`, **Then** all season/division/round/session/phase_result/audit rows for this server are deleted, server config row is preserved, APScheduler jobs for all deleted rounds are cancelled, and the bot responds with a success ephemeral message.
2. **Given** a server with an active season and config, **When** `/bot-reset confirm:CONFIRM full:True`, **Then** all rows including the server config row are deleted and the bot reports the server is now in a blank state requiring `/bot-init`.
3. **Given** `/bot-reset confirm:RESET full:False` (wrong confirmation string), **Then** the command is rejected with a descriptive error and no data is modified.
4. **Given** a server with no data at all, **When** `/bot-reset confirm:CONFIRM full:False`, **Then** the command succeeds with a "nothing to delete" response and no errors are raised.
5. **Given** a user without `Manage Server` permission, **When** `/bot-reset`, **Then** the command is rejected before any data is touched.
6. **Given** `/bot-reset confirm:CONFIRM full:True` on a server with active APScheduler jobs, **Then** all scheduled phase jobs for that server's rounds are cancelled before the rows are deleted.

### Edge Cases (addendum)

- What if the APScheduler job no longer exists when cancel is attempted (e.g., already fired)? → `cancel_round` already silently swallows missing-job errors; no additional handling needed.
- What if the DB has foreign-key constraints enabled and deletion order is wrong? → DELETE must traverse the dependency chain from leaf to root: `sessions/phase_results → rounds → divisions → seasons → (server_configs if full)`. Audit entries reference `server_id` directly and must be deleted before `server_configs`.
- What if a full reset is issued from the configured interaction channel? → The command uses `@admin_only` without `@channel_guard` (same pattern as `/bot-init`) so it works from any channel and remains accessible even after the config is deleted.

---

### Functional Requirements (addendum)

- **FR-011**: The bot MUST expose a `/bot-reset` slash command restricted to users with the Discord `Manage Server` permission (using existing `@admin_only` decorator, without `@channel_guard`).
- **FR-012**: `/bot-reset` MUST accept two parameters: `confirm: str` (required) and `full: bool` (optional, default `False`).
- **FR-013**: If `confirm` is not exactly `"CONFIRM"` (case-sensitive), the command MUST be rejected with an error before touching any data.
- **FR-014** *(renumbered from existing FR-014 — no conflict; existing ends at FR-010)*: When `full=False`, the command MUST delete all rows in `seasons`, `divisions`, `rounds`, `sessions`, `phase_results`, and `audit_entries` that belong to the invoking `server_id`. The `server_configs` row MUST NOT be deleted.
- **FR-015** *(addendum)*: When `full=True`, the command MUST additionally delete the `server_configs` row for the invoking server.
- **FR-016**: Before deleting any round rows, the command MUST cancel all APScheduler jobs associated with those rounds by calling `scheduler_service.cancel_round(round_id)` for each.
- **FR-017**: All deletions for a single reset MUST be executed within a single database transaction; a failure at any point MUST roll back all changes.
- **FR-018**: The command MUST respond ephemerally with a clear summary of what was deleted (number of seasons, divisions, rounds cleared) and, for full resets, a reminder to re-run `/bot-init`.
- **FR-019**: The README MUST document `/bot-reset` with its parameter table.

### Success Criteria (addendum)

- **SC-007**: `/bot-reset confirm:CONFIRM full:False` on a server with 1 active season, 2 divisions, and 3 rounds per division leaves the `server_configs` row intact and all 6 rounds' APScheduler jobs cancelled.
- **SC-008**: `/bot-reset confirm:CONFIRM full:True` removes the server's `server_configs` row; a subsequent `/season-status` returns "No active season found".
- **SC-009**: Passing any string other than `"CONFIRM"` is rejected before execution; the DB remains unchanged.
- **SC-010**: The reset command is inaccessible to users without `Manage Server` permission.


---

## Addendum — Correctness Fixes (2026-03-04)

### Functional Requirements (correctness fixes)

- **FR-020**: `/round-add` MUST reject any submission where `track` is empty or blank and `format` is not `MYSTERY`; the error message MUST name the format.
- **FR-021**: `/season-setup` MUST reject initialisation if the invoking server already has a physically present season row in the database (i.e., `has_existing_season()` returns True — any row not yet deleted, regardless of status) OR an in-memory pending setup exists; the error MUST be shown ephemerally. Rows removed by `/bot-reset` or the season-end deletion are gone entirely (hard-delete); after such removal `has_existing_season()` returns False and a new setup is permitted.
- **FR-022**: `/bot-reset` MUST also remove any in-memory pending season setup for the invoking server and cancel any pending `season_end` APScheduler job.
- **FR-023**: After every Phase 3 run, the bot MUST check whether all non-MYSTERY rounds for the active season have all three phases complete; if so, it MUST schedule a season-end job to fire 7 days after the latest round's `scheduled_at` timestamp.
- **FR-024**: When the season-end job fires (or is triggered immediately via test mode), the bot MUST attempt to post a log message to the configured log channel, then delete all season data for that server (equivalent to `/bot-reset confirm:CONFIRM full:False`). If the log channel cannot be resolved (not configured, or Discord channel deleted), the bot MUST emit a `logging.warning` to the bot console and proceed with deletion regardless — deletion MUST NOT be blocked by a missing channel.
- **FR-025**: In `bot.py`'s `on_ready` handler (after all cogs are loaded), the bot MUST scan the database for any server whose active season has all phases complete and attempt to re-register the season-end job using `last_round.scheduled_at + 7 days`. If that timestamp is already in the past (`now > fire_at`), the bot MUST call `execute_season_end` directly (immediate execution) rather than scheduling a future job, so that a prolonged outage does not permanently suppress a due deletion.
- **FR-026**: In test mode, when `/test-mode advance` is run on the last pending phase (Phase 3 of the last chronological round), the bot MUST immediately execute the season end (bypassing the 7-day delay) and cancel any just-scheduled season-end job before doing so.

### Success Criteria (correctness fixes)

- **SC-011**: `/round-add format:RACE track:<empty>` returns a descriptive error and does not create a round; `/round-add format:MYSTERY track:<empty>` succeeds.
- **SC-012**: A second `/season-setup` on a server with an existing approved (or pending-approval) season row is rejected ephemerally; a second attempt while a pending in-memory config exists is also rejected. After a `/bot-reset` or season-end deletion removes the row, a subsequent `/season-setup` on the same server MUST succeed.
- **SC-013**: After `/bot-reset`, a subsequent check of pending configs and APScheduler jobs shows no `season_end_{server_id}` job and no in-memory pending season for that server.
- **SC-014**: After Phase 3 runs for the last round, an APScheduler job `season_end_{server_id}` exists and is scheduled for `last_round.scheduled_at + 7 days`.
- **SC-015**: After a bot restart where a season was fully complete, the `season_end_{server_id}` job is re-registered within the bot's `on_ready` startup sequence.
- **SC-016**: `/test-mode advance` on the last Phase 3 immediately posts the season-complete log message and removes all season data, without waiting 7 days.

---

## Clarifications

### Session 2026-03-04

- Q: If the bot restarts before the season-end job fires, should pending season-end jobs be recovered? → A: Recover on restart — bot startup scans DB and re-schedules any due/pending season ends (FR-025, SC-015).
- Q: Should `has_existing_season()` block new setups based on soft-deleted / COMPLETED rows? → A: Hard-delete only; `has_existing_season()` returns False when no row exists (approved or pending-approval). After a season is deleted via reset or season-end, the row is gone and a fresh `/season-setup` is unblocked (FR-021 updated).
- Q: On startup recovery, if the season-end fire time is already in the past, what should happen? → A: Fire immediately — if `now > fire_at`, call `execute_season_end` directly during startup rather than scheduling (FR-025 updated).
- Q: Where should the FR-025 startup scan be attached? → A: `bot.py` `on_ready` — scan runs after all cogs are loaded, using `bot.season_service` and `bot.scheduler_service` (FR-025 updated).
- Q: If the configured log channel is missing or unresolvable when `execute_season_end` fires, what should happen? → A: Log to bot console only — emit `logging.warning` and proceed with deletion; the log message post is skipped but deletion is never blocked (FR-024 updated).
