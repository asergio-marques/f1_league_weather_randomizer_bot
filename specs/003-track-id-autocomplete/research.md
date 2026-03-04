# Research: Track ID Autocomplete & Division Command Cleanup

**Feature**: 003-track-id-autocomplete  
**Date**: 2026-03-04  
**Status**: Complete — no open unknowns

---

## R-001 — Discord.py autocomplete API

**Decision**: Use `@<command>.autocomplete("<param_name>")` decorator on an `async def` method that receives `(self, interaction, current: str)` and returns `list[app_commands.Choice[str]]` (max 25).

**Rationale**: The official discord.py 2.x autocomplete pattern. The callback fires on every keystroke as the user types; `current` holds the partial string typed so far. Returning `Choice(name=display_label, value=canonical_value)` lets the display label differ from the stored value — exactly what we need for `"27 – United Kingdom"` → `"United Kingdom"`.

**Alternatives considered**:
- Modal-based selection: not supported for slash command parameters.
- `app_commands.choices()` static decorator: requires a fixed list known at declaration time and cannot be filtered dynamically. Also hard-caps at 25, which is fine here (27 tracks) but the static list cannot be filtered interactively.

**Source**: discord.py docs § [Autocomplete](https://discordpy.readthedocs.io/en/stable/interactions/api.html#discord.app_commands.Command.autocomplete)

---

## R-002 — Handling > 25 tracks in autocomplete

**Decision**: Filter the 27-entry `TRACK_IDS` dict to entries whose `"ID – Name"` label contains `current` (case-insensitive), then return at most 25 results.

**Rationale**: Discord's API rejects more than 25 choices. With only 27 circuits, any two-character input (e.g., `"au"`) narrows the list well below 25. If `current` is empty, return the first 25 ordered by ID — the 27th entry (`27 – United Kingdom`) is only reachable by typing something.

**Alternatives considered**: Returning all 27 with no filtering: would violate the 25-choice limit on empty input. Sorting by relevance score: unnecessary complexity for 27 items.

---

## R-003 — Numeric ID resolution for manual (non-autocomplete) input

**Decision**: Before the canonical-name validator, attempt `TRACK_IDS.get(track.zfill(2), track)`. If found, replace the raw input with the canonical name; otherwise leave it as-is for the existing "unknown track" error path.

**Rationale**: Users who type `/round-add` in a client that doesn't support autocomplete, or who copy-paste a numeric code, should still get a clean resolution rather than a confusing "unknown track `5`" error.

**Alternatives considered**: Reject non-autocomplete input entirely: too strict; breaks accessibility on older clients.

---

## R-004 — Removing `race_day`/`race_time` from divisions

**Decision**: Drop the columns via a new migration (`003_remove_division_race_fields.sql`) using `ALTER TABLE divisions DROP COLUMN`. Remove from the `Division` model, `add_division()` service method, `SELECT` query, `_row_to_division` helper, and `PendingDivision` dataclass.

**Rationale**: `scheduled_at` on each `Round` already encodes the full race date and time. The division-level day/time were intended as a default fallback, but every round currently requires an explicit `scheduled_at`, making the division fields dead weight that confused administrators.

**SQLite compatibility note**: `ALTER TABLE … DROP COLUMN` is supported since SQLite 3.35.0 (2021-03-12). Python 3.8+ ships with SQLite ≥ 3.35 on all major platforms. If an older SQLite is detected the migration will raise — acceptable given the 3.8+ target.

**Alternatives considered**: Keep columns as NULLable but hidden from the command: adds dead schema weight and misleads future readers of the DB schema.

---

## R-005 — `bot_init` method name conflict

**Decision**: Rename `InitCog.bot_init` → `InitCog.handle_bot_init`. The `@app_commands.command(name="bot-init", ...)` decorator already sets the Discord-facing command name; the Python method name is only internal.

**Rationale**: discord.py's `Cog.__new__` raises `TypeError` for any method whose name starts with `cog_` or `bot_`, as these prefixes are reserved for Cog lifecycle hooks. The rename is the minimal, zero-risk fix.

**Alternatives considered**: Rename the slash command to avoid `bot-`: would break any existing bookmarks/muscle memory of server admins with no benefit.


---

## Addendum — Bot Data Reset Command

### R-006 — FK-Safe Deletion Order

**Question**: In what order must rows be deleted to respect foreign-key constraints?

**Decision**: Delete leaf tables first and cascade toward root:
1. `sessions` WHERE `round_id` IN (server's rounds)
2. `phase_results` WHERE `round_id` IN (server's rounds)
3. `rounds` WHERE `division_id` IN (server's divisions)
4. `divisions` WHERE `season_id` IN (server's seasons)
5. `seasons` WHERE `server_id = ?`
6. `audit_entries` WHERE `server_id = ?`
7. (full only) `server_configs` WHERE `server_id = ?`

**Rationale**: SQLite FK enforcement (enabled via `PRAGMA foreign_keys = ON`) rejects parent-before-child deletions. Querying intermediate IDs up front avoids correlated sub-selects across every DELETE.

**Alternatives considered**: `PRAGMA foreign_keys = OFF` during operation — rejected; undermines integrity guarantees.

---

### R-007 — Single-Transaction Strategy

**Question**: Should the reset execute all DELETEs in one DB transaction?

**Decision**: Yes — wrap every DELETE in a single `async with db:` block; roll back entirely on any exception.

**Rationale**: Partial deletion (e.g., seasons gone but divisions still present) would corrupt the server's data in an unrecoverable way. Atomicity is non-negotiable.

**Alternatives considered**: Per-table commits — rejected; leaves DB in inconsistent state on failure.

---

### R-008 — Cancel APScheduler Jobs Before DELETE

**Question**: Must scheduled jobs be cancelled before the rows they reference are deleted?

**Decision**: Yes — call `scheduler_service.cancel_round(round_id)` for every round belonging to the server *before* opening the DB transaction.

**Rationale**: Leaving dangling APScheduler jobs referencing deleted `round_id` values risks callback errors after reset. `cancel_round()` already silently ignores missing jobs, so pre-cancellation is safe even for already-fired phases.

**Alternatives considered**: Cancel after DELETE — rejected; window exists where the scheduler fires against deleted rows.

---

### R-009 — `@admin_only` Without `@channel_guard`

**Question**: Should `/bot-reset` require the configured bot channel like other commands?

**Decision**: No `@channel_guard`. Apply `@admin_only` only (mirrors `/bot-init` pattern).

**Rationale**: After a full reset the `server_configs` row is deleted, making `channel_guard` unable to look up the permitted channel. The command must remain accessible from any channel so admins can recover. Partial reset also clears seasons/divisions, so enforcing a now-meaningless channel config adds no security benefit.

**Alternatives considered**: Store channel ID separately from `server_configs` — over-engineered for a one-shot administrative command.
