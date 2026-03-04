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
