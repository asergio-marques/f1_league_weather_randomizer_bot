# Research: Module System — Weather & Signup Modules

**Feature Branch**: `013-module-system`  
**Produced by**: Phase 0 of `/speckit.plan`

---

## 1. Module State Persistence Strategy

**Question**: How should per-server module enabled/disabled state be stored?

**Decision**: Extend the existing `server_configs` table with boolean columns
(`weather_module_enabled`, `signup_module_enabled`). Do NOT create a generic
`server_module_config` join table — the module set is small and fixed for now;
sparse boolean columns are simpler, migration-safe, and readable.

**Rationale**: The project uses raw SQL migrations (no ORM). A generic join table
would require joins on every module check hot path. Adding a column per module
matches the existing pattern (e.g. `test_mode_active` column). When a new module
is ratified in the future, a new migration adds a column — the cost is trivially low.

**Alternatives considered**:
- JSON blob in a single column: hard to query, non-auditable in raw SQLite tools.
- Separate `server_module_states` table: correct for many modules but premature
  with only two modules; adds unnecessary join complexity today.

---

## 2. Signup Module Configuration Storage

**Question**: Where should the signup module's channel, roles, and settings live?

**Decision**: Two additional tables:
- `signup_module_config` — stores `server_id`, `signup_channel_id`, `base_role_id`,
  `signed_up_role_id`, `signups_open` (boolean), and the selected tracks for the open
  signup window (stored as a separate `signup_window_tracks` table or a JSON blob).
- `signup_module_settings` — stores `server_id`, `nationality_required` (bool),
  `time_type` (TEXT enum), `time_image_required` (bool).

Tracks for the open signup window are low-cardinality (up to ~24 track IDs). Storing
them as a comma-separated list in a `selected_tracks_json` TEXT column is acceptable;
the data is only read/written atomically (on open/close) not queried per-track.

**Rationale**: Separating signup module settings from the core `server_configs` row
keeps the core table stable and adheres to Principle X's module config isolation rule.
Settings survive enable/disable cycles (cleared on disable only if explicitly
specified — the spec requires full config clear on disable, so `signup_module_config`
is deleted; `signup_module_settings` may optionally be preserved or cleared — spec says
"clearing all settings from the previous enabling", so they are cleared on disable).

**Alternatives considered**:
- Add columns to `server_configs`: violates Principle X module config isolation.
- Single merged config table: conflates structural (channel/role) with behavioural
  (settings toggles); harder to wipe cleanly.

---

## 3. Availability Time Slots Storage & ID Recomputation

**Question**: How should time slots be stored given that IDs are recomputed on every mutation?

**Decision**: Store time slots in a `signup_availability_slots` table with columns
`(id INTEGER PK AUTOINCREMENT, server_id, day_of_week INTEGER, time_hhmm TEXT)`.
The `id` primary key is a stable internal surrogate and NOT the user-visible slot ID.
The user-visible slot ID is the 1-based rank of each slot in the chronological sort
`ORDER BY day_of_week ASC, time_hhmm ASC`. The service layer computes this rank on
every read. On remove, delete the row by surrogate PK; ranks recompute automatically
on next read.

**Rationale**: If the user-visible ID were stored as a column, every removal would
require an UPDATE sweep across all rows to close the gap. Computed rank is derived
on read (O(n) where n is small, expected 3–15 slots); no update sweep is needed.
There is no risk of stale IDs in driver wizard answers because slot mutations are
gated behind "signups must be closed" (FR-026).

**Day-of-week encoding**: Monday = 1, Tuesday = 2, …, Sunday = 7 (ISO 8601 weekday).

**Time representation**: 24-hour HH:MM stored as a TEXT `HH:MM` string. This sorts
correctly as a plain string within the same day. The service layer parses 12-hour AM/PM
input and normalises to HH:MM before persistence.

**Alternatives considered**:
- Storing rank in the DB: requires sweep updates on every mutation.
- Using a natural sort key (integer minutes-since-week-start): correct and compact, but
  less human readable in raw DB inspection; TEXT HH:MM serves the same purpose with
  better readability.

---

## 4. Weather Module Enable — Overdue Phase Execution

**Question**: How should "catch up" execution work when the weather module is enabled mid-season
with overdue phase horizons?

**Decision**: On `module enable weather`:
1. Query all non-Mystery rounds of the active season where `scheduled_at` is in the future
   (or whose phase windows have passed). For each round, determine which phases are overdue
   (`phase_horizon < utcnow()`) and not yet completed (no `PhaseResult` row with status
   `COMPLETED` for that phase).
2. Execute overdue phases sequentially (Phase 1 → Phase 2 → Phase 3) **synchronously within
   the enable command's interaction lifecycle** using `discord.Interaction.followup` (deferred
   response). If Phase 1 fails, Phase 2 is not attempted.
3. After catch-up, schedule future-horizon jobs for all remaining phases via
   `SchedulerService.schedule_round()` using `replace_existing=True`.

**Why synchronous in the interaction lifecycle**: The spec requires acknowledging the command
within 3 seconds (Bot Behavior Standards). Use `await interaction.response.defer(ephemeral=True)`
immediately then `followup.send(...)` after all phases complete. APScheduler's past-date
`DateTrigger` already fires missed jobs immediately on scheduler restart, but that mechanism
depends on the scheduler being stopped during the window — here we need deterministic ordering
(Phase 1 before Phase 2), so explicit orchestration is cleaner and more auditable.

**Failure behaviour**: If a phase fails during catch-up (e.g., a missing forecast channel per
FR-012), the enable operation itself fails — module state is NOT saved as enabled. An audit
entry records the failure. The admin must fix the channel configuration and retry.

**Alternatives considered**:
- Dispatch catch-up as background tasks: non-deterministic ordering, harder to surface failures
  in the command response.
- Rely solely on APScheduler `misfire_grace_time`: APScheduler fires past triggers immediately
  when the scheduler starts, but cannot guarantee Phase 1 fires before Phase 2 if both are
  overdue at the same instant. Explicit sequential execution is more reliable.

---

## 5. Discord Channel Permission Management

**Question**: How should the bot apply and remove signup channel permissions?

**Decision**: Use `discord.TextChannel.set_permissions(target, overwrite)` to create explicit
`PermissionOverwrite` entries per role:
- `@everyone` role: `view_channel=False` (deny all by default).
- `base_role`: `view_channel=True, send_messages=False, add_reactions=False`.
- Trusted role (interaction_role_id): `view_channel=True, send_messages=True`.
- Bot's own member: `view_channel=True, send_messages=True, manage_channels=True`.
- Server owner / roles with `manage_guild`: inherited from guild-level permissions, no explicit
  overwrite needed (guild admins bypass channel overwrites in Discord).

On disable, call `channel.set_permissions(target, overwrite=None)` for each role the bot added,
resetting those overwrites. The bot only removes overwrites it applied — it does not clear
pre-existing non-bot overwrites.

**Bot required intents/permissions**: `manage_channels` (or `manage_roles`) at the guild level.
The permission scope must be in the bot's invite URL. This is noted as an assumption in the spec.

**Alternatives considered**:
- Using category-level permissions: would affect all channels in the category, over-broad.
- Storing which overwrites were applied (to know what to undo): unnecessary; the bot applies a
  fixed set of overwrites identified by known role IDs — a simple reverse-apply undoes them.

---

## 6. `forecast_channel` Conditionality in `division add`

**Decision** (confirmed by user, FR-012):

`forecast_channel` becomes an **optional** parameter. Validation logic at the command level:

| Weather module state | `forecast_channel` supplied | Outcome |
|----------------------|-----------------------------|---------|
| Enabled              | Yes                         | Accepted |
| Enabled              | No                          | Error: "weather module is active — forecast channel required" |
| Disabled             | No                          | Accepted |
| Disabled             | Yes                         | Error: "weather module is inactive — do not supply a forecast channel now" |

Additionally, `module enable weather` must pre-validate that all existing divisions for the
server's active season (if any) have a non-null `forecast_channel_id`. If any division is missing
one, the enable command fails and lists the offending divisions.

**Impact on `Division` model**: `forecast_channel_id` column becomes nullable (NULL = no channel
configured). The model dataclass updates `forecast_channel_id: int | None`.

**Migration**: `ALTER TABLE divisions ALTER COLUMN forecast_channel_id` to allow NULL, or — since
SQLite does not support `ALTER COLUMN` — create a new migration that recreates the table with
`forecast_channel_id INTEGER` (no `NOT NULL`). Existing rows keep their values; new rows may
have NULL.

---

## 7. `channel_guard` and Access Tiers for New Commands

**Question**: Which access tier gates which new commands?

**Mapping** (confirmed from spec FRs and constitution Principle I):

| Command group | Access tier | Decorator |
|---------------|-------------|-----------|
| `/module enable weather` | Server admin (Manage Server) | `@channel_guard @admin_only` |
| `/module disable weather` | Server admin (Manage Server) | `@channel_guard @admin_only` |
| `/module enable signup`   | Server admin (Manage Server) | `@channel_guard @admin_only` |
| `/module disable signup`  | Server admin (Manage Server) | `@channel_guard @admin_only` |
| `/signup nationality toggle` | Server admin (Manage Server) | `@channel_guard @admin_only` |
| `/signup time-type toggle` | Server admin (Manage Server) | `@channel_guard @admin_only` |
| `/signup time-image toggle` | Server admin (Manage Server) | `@channel_guard @admin_only` |
| `/signup time-slot add` | Interaction role (tier 2 trusted) | `@channel_guard` + trusted_role check |
| `/signup time-slot remove` | Interaction role (tier 2 trusted) | `@channel_guard` + trusted_role check |
| `/signup enable` | Interaction role (tier 2 trusted) | `@channel_guard` + trusted_role check |
| `/signup disable` | Interaction role (tier 2 trusted) | `@channel_guard` + trusted_role check |

Note: There is currently no `trusted_only` decorator — it exists only as an implicit subset of
the interaction role. The `channel_guard` decorator verifies the interaction role; trusted
(tier 2) commands additionally verify `manage_guild` permission OR a separate
`trusted_role_id` if one is ever introduced. For now, tier 2 trusted commands use
`@channel_guard @admin_only` per the existing bot convention (server admins are the trusted
config tier). This aligns with Principle I Tier-2 semantics as currently implemented.

---

## 8. `SchedulerService` — New `cancel_all_for_server` Method

**Question**: How should "cancel all weather jobs for a server" work given that job IDs are
round-scoped (`phase1_rN`, `phase2_rN`, `phase3_rN`, `mystery_rN`, `cleanup_rN`)?

**Decision**: Add a `cancel_all_weather_for_server(server_id: int)` method to
`SchedulerService`. Implementation: query all rounds for all active/setup seasons of
`server_id`, then call `cancel_round(round_id)` for each. The query happens inside the service
via `db_path` (same pattern as other service methods). This keeps the scheduler self-contained.

**Alternatives considered**:
- Introspecting APScheduler's job store to filter by job-ID prefix: fragile if job naming
  conventions change.
- Passing explicit round IDs from the cog: puts DB knowledge in the cog; violates separation
  of concerns.

---

## 9. Driver State Machine Extension (FR-037)

**New transitions required** (not yet in `DriverService`):
- `PENDING_SIGNUP_COMPLETION → NOT_SIGNED_UP` (forced close by admin via signup disable)
- `PENDING_DRIVER_CORRECTION → NOT_SIGNED_UP` (forced close by admin via signup disable)

These are additive to the existing transitions in `driver_service.py`. The `DriverService`
transition guard must be updated to permit these two new edges. No new migration is needed
(state values are already defined in `DriverState` enum; the state machine is enforced in
Python, not via DB constraints).

---

## 10. Signup Window State — Initiation Button Message Persistence

**Question**: The spec requires the bot to delete the "signup button" message when signups close.
How should the message ID be tracked?

**Decision**: Store the `signup_button_message_id` (Discord snowflake ID) in the
`signup_module_config` table. When signups open, the bot posts the button, captures the
message ID from the `discord.Message` return value, and persists it. When signups close,
the bot fetches the channel and deletes the message by ID. If the message is already gone
(e.g., manually deleted by an admin), catch `discord.NotFound` and continue gracefully.

---

## Summary of Research Decisions

| # | Decision |
|---|----------|
| 1 | Module state: boolean columns on `server_configs` table |
| 2 | Signup config: two new tables (`signup_module_config`, `signup_module_settings`) |
| 3 | Time slots: surrogate PK table; user-visible ID is computed rank on read |
| 4 | Weather catch-up: sequential synchronous execution in deferred interaction |
| 5 | Channel permissions: per-role `PermissionOverwrite`; reversed on disable |
| 6 | `forecast_channel`: optional, mutually gated by weather module state (FR-012) |
| 7 | Access tiers: all module and signup-settings commands use `admin_only`; slot/open/close use `channel_guard` |
| 8 | Cancel-all weather jobs: new `cancel_all_weather_for_server()` on `SchedulerService` |
| 9 | Driver SM extension: add two new transitions in `DriverService` |
| 10 | Button message ID: persisted in `signup_module_config` |
