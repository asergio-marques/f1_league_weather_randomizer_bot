# Research: Driver Profiles, Teams & Season Enhancements

**Phase 0 Output** | Feature: `012-driver-profiles-teams` | Date: 2026-03-06

All NEEDS CLARIFICATION items resolved. No new Python packages required.

---

## 1. State Machine Enforcement

**Decision**: Encode the allowed transitions as a Python `dict[DriverState, set[DriverState]]`
inside `DriverService`. A single `transition(driver_id, new_state)` method checks the map,
raises a domain error on invalid transitions, and applies the change + audit log entry in one
transaction.

**Rationale**: A static dict is the simplest representation of a deterministic finite automaton.
It is trivially unit-testable (enumerate every pair), requires no external library, and the
closed-world assumption (all unlisted transitions are forbidden) matches the spec.

**Alternatives considered**:
- transitions / pytransitions library: would add a dependency for a graph that is fully known
  at design time and has no event-driven complexity. Rejected — YAGNI.
- Database trigger for state enforcement: harder to test, bypasses Python error handling.
  Rejected.

**Allowed transitions table** (reproduced from spec for reference):

| From | To | Condition |
|---|----|-----------|
| NOT_SIGNED_UP | PENDING_SIGNUP_COMPLETION | normal |
| PENDING_SIGNUP_COMPLETION | PENDING_ADMIN_APPROVAL | normal |
| PENDING_ADMIN_APPROVAL | UNASSIGNED | normal |
| PENDING_ADMIN_APPROVAL | PENDING_DRIVER_CORRECTION | normal |
| PENDING_DRIVER_CORRECTION | PENDING_ADMIN_APPROVAL | normal |
| PENDING_ADMIN_APPROVAL | NOT_SIGNED_UP | normal |
| UNASSIGNED | ASSIGNED | normal |
| * (not LEAGUE_BANNED, not SEASON_BANNED) | SEASON_BANNED | normal |
| * (not LEAGUE_BANNED) | LEAGUE_BANNED | normal |
| SEASON_BANNED | NOT_SIGNED_UP | normal |
| LEAGUE_BANNED | NOT_SIGNED_UP | normal |
| NOT_SIGNED_UP | UNASSIGNED | test mode only |
| NOT_SIGNED_UP | ASSIGNED | test mode only |

"*" rows: implemented as a blocklist check (`current_state not in {LEAGUE_BANNED}` etc.)
rather than an exhaustive allowlist, since the source spec uses "All States except…" wording.

---

## 2. Auto-Deletion Rule Implementation

**Decision**: In `DriverService.transition()`, after persisting state = NOT_SIGNED_UP, check
`former_driver`. If `False`, issue `DELETE FROM driver_profiles WHERE id = ?` in the same
`async with get_connection(...)` block (same transaction). If the driver has active
`team_seat` references, clear `driver_id` on those rows first to avoid FK violations.

**Rationale**: Keeping the deletion in the same transaction as the state change guarantees
atomicity (Constitution Principle VIII). Clearing seat references first respects FK constraints.

**Alternatives considered**: A deferred cleanup job — rejected because it could leave orphan
profiles visible transiently, violating atomicity guarantees.

---

## 3. Discord User ID Type

**Decision**: Store `discord_user_id` as `TEXT` (not INTEGER) in the `driver_profiles` table.
Using it as the table's natural key within a server context via a composite primary key
`(server_id, discord_user_id)`.

**Rationale**: Discord snowflake IDs fit in a 64-bit unsigned int, but SQLite's INTEGER
affinity is signed 64-bit. An unsigned 64-bit value above 2^63−1 would lose precision if
stored as INTEGER. TEXT storage is safe, unambiguous, and consistent with how discord.py
surfaces `user.id` as a string in some contexts. The existing `audit_entries.actor_id` column
uses INTEGER — this feature will not change that column, but new driver_profile key will use
TEXT to be safe.

**Alternatives considered**: INTEGER — rejected due to potential sign overflow for large
Discord snowflakes above 9,223,372,036,854,775,807.

---

## 4. Team Seat Count & Reserve Representation

**Decision**: Represent `max_seats` as `INTEGER` on `team_instances`. Use the sentinel value
`-1` (or `NULL`) to mean "unlimited" for the Reserve team. Enforce in `TeamService` that
seats are never added beyond `max_seats` (skipping the check when `max_seats = -1`).

**Rationale**: A nullable/sentinel integer in one column is simpler than a separate boolean
or a second table for unconstrained teams. The -1 sentinel is idiomatic in several Python
standard library contexts (e.g., `maxlen=-1` in some collections).

**Alternatives considered**: Separate `is_reserve BOOLEAN` column — adds redundancy since
"Reserve" is already identified by name and a protected flag. Rejected — single sentinel
is sufficient.

---

## 5. Season Counter Storage

**Decision**: Add `previous_season_number INTEGER NOT NULL DEFAULT 0` column to
`server_configs` via `ALTER TABLE`. Increment it inside `SeasonService.complete_season()`
and `SeasonService.cancel_season()`. The display number exposed in all bot output is
fetched from `server_configs.previous_season_number + 1` during an active season, or
stored directly on the `seasons` row as `season_number` (set at creation time).

**Rationale**: Storing the number on the season row at creation time means it never drifts
even if the server_configs counter is modified (e.g., during a reset). The counter on
server_configs is the source of truth for "what the next season number will be".

**Alternatives considered**: Computing season number dynamically by counting historical
season rows — fragile if seasons are deleted by /bot-reset. Rejected.

---

## 6. Division Tier: Sequential Gate Algorithm

**Decision**: On season approval, fetch all division tier values for the season, sort them,
and compare against `range(1, len(tiers) + 1)`. If they differ, reject with an error
message that lists the specific missing tiers (e.g., "Missing tier(s): 2, 4").

Algorithm:
```python
tiers = sorted(d.tier for d in divisions)
expected = list(range(1, len(tiers) + 1))
missing = sorted(set(expected) - set(tiers))
extra   = sorted(set(tiers) - set(expected))  # handles duplicates / out-of-range
```

**Rationale**: O(n log n) sort + O(n) set comparison is trivially fast for the expected
number of divisions per season (2–10). The error message names missing tiers explicitly,
satisfying SC-004.

**Alternatives considered**: Checking only for gaps (consecutive pair scan) — misses the
"doesn't start at 1" case. Rejected.

---

## 7. Storing DB Ordering for Divisions

**Decision**: Order divisions by `tier ASC` in all SELECT queries that return division lists.
Do not add a dedicated `sort_order` column — `tier` already encodes the display order.
Add `ORDER BY tier ASC` to all relevant queries in `SeasonService`.

**Rationale**: `tier` is the canonical sort key per spec. A separate column would be
redundant and could drift out of sync.

---

## 8. Season Team Command Atomicity (multi-division mutation)

**Decision**: In `TeamService.season_team_add/modify/remove()`, fetch all division IDs for
the SETUP season in a single query, then apply the team mutation to each division inside a
single transaction (all within one `get_connection` context manager). If any division fails,
the entire operation rolls back.

**Rationale**: RFC FR-016 requires all-or-nothing semantics across all divisions in a
single command. SQLite's implicit transaction handles this as long as all statements are
inside the same connection context before `commit()`.

---

## 9. Migration Numbering

**Decision**: New migration file is `008_driver_profiles_teams.sql`. It contains:
- `ALTER TABLE server_configs ADD COLUMN previous_season_number ...`
- `ALTER TABLE seasons ADD COLUMN season_number ...`
- `ALTER TABLE divisions ADD COLUMN tier ...`
- `CREATE TABLE driver_profiles (...)`
- `CREATE TABLE driver_season_assignments (...)`
- `CREATE TABLE driver_history_entries (...)`
- `CREATE TABLE default_teams (...)`
- `CREATE TABLE team_instances (...)`
- `CREATE TABLE team_seats (...)`

**Rationale**: All logically coupled changes belong in one migration to avoid intermediate
states where, e.g., `driver_profiles` exists but `team_seats` does not. The existing
migration runner applies scripts in sorted filename order; `008_` follows `007_`.

---

## 10. New Cog for Driver Commands

**Decision**: Create `src/cogs/driver_cog.py` with a `/driver` app_commands.Group.
Initially contains one subcommand: `reassign`. Future driver commands (ban, unban, etc.)
will be added to this group in subsequent features.

**Rationale**: Follows the established `/domain action` convention (Constitution Bot
Behavior Standards). Placing it in a dedicated cog keeps SeasonCog from growing further.

---

## 11. Test-Mode Set-Former-Driver Command Location

**Decision**: Add `/test-mode set-former-driver` as a new subcommand to the existing
`TestModeCog.test_mode` Group in `src/cogs/test_mode_cog.py`.

**Rationale**: It is test-mode-gated, consistent with `advance` and `review` subcommands
already on this group. No new cog required.

---

## All NEEDS CLARIFICATION items: RESOLVED

No items required external clarification. All decisions above are derived from:
- The feature spec (FR-001–FR-025, Assumptions 1–8, Constraints)
- The constitution (Principles I–IX)
- The existing codebase patterns (service layer, migrations, channel_guard, admin_only)
