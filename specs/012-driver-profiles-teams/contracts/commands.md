# Command Contracts: Driver Profiles, Teams & Season Enhancements

**Phase 1 Output** | Feature: `012-driver-profiles-teams` | Date: 2026-03-06

This document describes the Discord slash command interface introduced or modified by this
feature. Only the four `<NEW COMMAND>` items add new commands; all other changes modify
the behaviour of existing commands.

All commands follow the `/domain action` subcommand-group convention (Constitution Bot
Behavior Standards). All responses are ephemeral unless noted.

---

## New Commands

---

### `/driver reassign`

**Group**: `/driver` (new app_commands.Group, `src/cogs/driver_cog.py`)  
**Access**: `@admin_only` (Tier-2 trusted/config role)  
**Channel**: interaction channel only (enforced by `@channel_guard`)  
**Interaction**: single — no wizard

**Purpose**: Update the Discord User ID associated with an existing driver profile, covering
the case where a league member changes their Discord account.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `old_user` | `discord.Member` OR raw User ID text | Yes | The existing Discord user whose profile is to be re-keyed. Accept a `@mention` (resolved to a `discord.Member`) or a raw snowflake string to handle users who have left the server. |
| `new_user` | `discord.Member` | Yes | The target Discord account. Must not already have a driver profile. |

**Pre-conditions checked (reject with ephemeral error if violated)**:
1. A driver profile exists for `old_user` in this server.
2. No driver profile exists for `new_user` in this server.
3. Invoker holds the Tier-2 admin role.

**Success response** (ephemeral):
```
✅ Driver profile re-keyed successfully.
   Old User ID : {old_discord_user_id}
   New User ID : {new_discord_user_id}
   State       : {current_state}
   Former driver: {Yes | No}
```

**Audit log entry produced**: `change_type = "DRIVER_USER_ID_REASSIGN"`,
`old_value = "{old_user_id}"`, `new_value = "{new_user_id}"`.

**Errors returned**:

| Condition | Message |
|-----------|---------|
| No profile for old_user | `⛔ No driver profile found for user {old_user_id} on this server.` |
| Profile already exists for new_user | `⛔ User {new_user_id} already has a driver profile on this server. Reassignment is not permitted.` |
| Insufficient role | Standard `@admin_only` message |

---

### `/test-mode set-former-driver`

**Group**: `/test-mode` (existing, `src/cogs/test_mode_cog.py`)  
**Access**: `@admin_only`  
**Channel**: interaction channel only  
**Interaction**: single

**Purpose**: Manually set the `former_driver` flag on a driver profile to `true` or `false`.
Only available when test mode is active.

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `user` | `discord.Member` | Yes | The driver whose flag is being updated. |
| `value` | `bool` (True / False) | Yes | The new value for the `former_driver` flag. |

**Pre-conditions checked**:
1. Test mode is currently enabled for this server.
2. A driver profile exists for `user` in this server.
3. Invoker holds the Tier-2 admin role.

**Success response** (ephemeral):
```
✅ former_driver flag updated.
   User    : {user_mention}
   Old value: {True | False}
   New value: {True | False}
```

**Audit log entry produced**: `change_type = "TEST_FORMER_DRIVER_FLAG_SET"`,
`old_value = "{old_bool}"`, `new_value = "{new_bool}"`.

**Errors returned**:

| Condition | Message |
|-----------|---------|
| Test mode disabled | `⛔ This command is only available when test mode is enabled.` |
| No profile for user | `⛔ No driver profile found for {user_mention} on this server.` |
| Insufficient role | Standard `@admin_only` message |

---

### `/team default`

**Group**: `/team` (new app_commands.Group, `src/cogs/team_cog.py` OR added to an existing
cog — see note below)  
**Subcommand**: `default` with actions `add`, `rename`, `remove`  
**Access**: `@admin_only`  
**Channel**: interaction channel only  
**Interaction**: single per action

> **Note**: Because Constitution Bot Behavior Standards require a `/domain action` pattern,
> and team management spans both server-defaults and season-scope, a new `/team` group is
> created. This is the only way to group both `default` and `season` subcommands cleanly.
> New cog: `src/cogs/team_cog.py`.

**Purpose**: Manage the server-level default team list that seeds new divisions.

#### `/team default add`

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | Yes | Name of the new team (max 50 chars). |
| `seats` | integer | No | Number of seats. Defaults to 2. Must be ≥ 1. |

**Pre-conditions**: Team name must not already exist in this server's default list.

**Success response**:
```
✅ Default team "{name}" added ({seats} seats).
```

**Errors**:

| Condition | Message |
|-----------|---------|
| Name already exists | `⛔ A default team named "{name}" already exists.` |
| Reserved name "Reserve" | `⛔ The team name "Reserve" is protected and cannot be managed.` |

#### `/team default rename`

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `current_name` | string | Yes | Exact current name of the team. Autocomplete from existing defaults. |
| `new_name` | string | Yes | Replacement name (max 50 chars). |

**Pre-conditions**: `current_name` must exist and not be Reserve; `new_name` must not
already exist.

**Success response**:
```
✅ Default team "{current_name}" renamed to "{new_name}".
```

#### `/team default remove`

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | Yes | Exact name of the team to remove. Autocomplete from existing defaults. |

**Pre-conditions**: Team must exist and not be Reserve.

**Confirm/cancel prompt** (ephemeral, before execution):
```
⚠️ Remove default team "{name}"?
   This will not affect team instances already created in existing divisions.
   [Confirm] [Cancel]
```

**Success response**:
```
✅ Default team "{name}" removed from server defaults.
```

---

### `/team season`

**Group**: `/team` (same group as above)  
**Subcommands**: `add`, `rename`, `remove`  
**Access**: `@admin_only`  
**Channel**: interaction channel only  
**Lifecycle gate**: Season must be in SETUP state.

**Purpose**: Apply team configuration changes to all divisions of the current season
simultaneously.

#### `/team season add`

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | Yes | Name of the team to add. |
| `seats` | integer | No | Number of seats. Defaults to 2. |

**Pre-conditions**: A SETUP season must exist; team name must not already exist in any
division of that season; name must not be "Reserve".

**Success response**:
```
✅ Team "{name}" added to all {n} division(s) of Season {season_number}.
```

#### `/team season rename`

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `current_name` | string | Yes | Exact current name (same across all divisions). |
| `new_name` | string | Yes | New name. |

**Pre-conditions**: Season in SETUP; `current_name` exists in all divisions and is not
Reserve.

**Success response**:
```
✅ Team "{current_name}" renamed to "{new_name}" across all {n} division(s).
```

#### `/team season remove`

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | Yes | Exact team name. |

**Pre-conditions**: Season in SETUP; team exists and is not Reserve.

**Confirm/cancel prompt**:
```
⚠️ Remove team "{name}" from all {n} division(s) of Season {season_number}?
   Any seat assignments for this team will also be removed.
   [Confirm] [Cancel]
```

**Success response**:
```
✅ Team "{name}" removed from all {n} division(s) of Season {season_number}.
```

**Errors** (all `/team season` subcommands):

| Condition | Message |
|-----------|---------|
| No SETUP season | `⛔ No season is currently in setup. Team configuration can only be changed during season setup.` |
| Season ACTIVE or COMPLETED | Same as above |
| Name is "Reserve" | `⛔ The Reserve team is protected and cannot be modified.` |

---

## Modified Commands

---

### `/division add` (existing, `SeasonCog`)

**Change**: New required parameter `tier` (integer).

**New parameter**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `tier` | integer | Yes | Tier of this division (1 = highest). Must be ≥ 1. Must not conflict with an existing division tier in the same season. |

**Additional error**:

| Condition | Message |
|-----------|---------|
| Tier already used in this season | `⛔ A division with tier {tier} already exists in this season.` |
| Missing tier | Discord enforces this since the parameter is marked required. |

**Side effect**: On successful creation, `SeasonService` copies all `default_teams` rows
for this server into `team_instances` rows for the new division, and pre-creates `team_seats`
rows (2 per configurable team). Reserve instance is created with `max_seats = -1`; no seats
created for Reserve at this stage (assigned on demand in a future feature).

---

### `/division duplicate` (existing, `SeasonCog`)

**Change**: New required parameter `tier` (integer), same validation as `/division add`.

---

### `/season approve` (existing, `SeasonCog`)

**Change**: Before executing approval, validate that division tiers form a gapless sequence
starting at 1. On failure, reject with a diagnostic message listing missing tiers.

**New error**:

| Condition | Message |
|-----------|---------|
| Tier sequence invalid | `⛔ Season cannot be approved. Division tiers are not sequential. Missing tier(s): {list}. Current tiers: {list}. Please correct the division tiers and try again.` |

---

### `/season review` (existing, `SeasonCog`)

**Change**: Extended output — each division section now includes a team roster.

**New output section per division**:
```
── Division: {name} (Tier {tier}) ──
  ...existing round info...

  Teams:
    🏎️  {team_name}  — Seat 1: {driver_mention | unassigned}  |  Seat 2: {driver_mention | unassigned}
    🏎️  {team_name}  — Seat 1: {driver_mention | unassigned}  |  Seat 2: {driver_mention | unassigned}
    🏎️  Reserve      — (no seats pre-assigned)

  Unassigned drivers: {driver_mention, ...  | none}
```

---

### `/season setup` (existing, `SeasonCog`)

**Change**: The newly created season now gets `season_number = server_config.previous_season_number + 1`.
Displayed number appears in the setup confirmation message.

---

### `/season cancel` and `/season approve` → completion path (existing, `SeasonCog` / `SeasonEndService`)

**Change**: After persisting the CANCELLED or COMPLETED status, increment
`server_configs.previous_season_number` by 1.
