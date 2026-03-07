# Command Contract: `/module` Group

**Feature**: 013-module-system  
**Cog**: `src/cogs/module_cog.py`  
**Access Tier**: Server Admin (`@channel_guard @admin_only`)

---

## Command Tree

```
/module
├── enable  <module_name>
└── disable <module_name>
```

`module_name` is a `discord.app_commands.Choice[str]` with values:
- `"weather"`
- `"signup"`

---

## `/module enable <module_name>`

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `module_name` | `Choice[str]` | Yes | `"weather"` or `"signup"` |

**Additional parameters when `module_name == "signup"` (required for that branch):**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `channel` | `discord.TextChannel` | Yes (signup only) | The text channel to use as the signup channel |
| `base_role` | `discord.Role` | Yes (signup only) | Role held by all members eligible to sign up (view-only overwrite applied) |
| `signed_up_role` | `discord.Role` | Yes (signup only) | Role granted on successful signup completion (stored for future wizard use) |

These three parameters are declared as optional on the slash command (Discord does not support conditional required params), but the command handler returns an error if any are missing when `module_name == "signup"`.

### Preconditions

**Common (both modules)**:
- Server config exists (bot is initialised).
- Interaction originates from the configured interaction channel.
- Caller has `MANAGE_GUILD` permission.
- Module is not already enabled (idempotency guard: error message only, not raise).

**Weather module only**:
- If an active season exists with divisions: every division must have `forecast_channel_id IS NOT NULL`. If any division lacks a channel, the command fails and lists offending division names.
- _(No block if no active season exists — enables fine with no season.)_

**Signup module only**:
- A `signup_module_config` row must exist for this server (i.e. the module has been configured via `/signup config` before enabling). If missing, error: _"Signup module not configured — run `/signup config` first."_
- The bot must have `manage_channels` (or `manage_roles`) permission on the configured signup channel.

### Behaviour

#### Weather enable
1. Mark `server_configs.weather_module_enabled = 1`.
2. If an active season exists: run catch-up for any overdue phase horizons sequentially (Phase 1 → 2 → 3 per round). Any failure aborts the enable and reverts the flag.
3. Schedule all future-horizon jobs via `SchedulerService.schedule_round()` for every round of the active season.
4. Reply ephemeral: _"✅ Weather module enabled."_

#### Signup enable
1. Apply Discord channel permission overwrites to `signup_channel_id` (see data-model §6.2).
2. Mark `server_configs.signup_module_enabled = 1`.
3. Reply ephemeral: _"✅ Signup module enabled."_

### Error Responses (ephemeral)

| Condition | Message |
|-----------|---------|
| Module already enabled | _"Weather / Signup module is already enabled."_ |
| Division(s) missing forecast channel | _"Weather module cannot be enabled — the following divisions are missing a forecast channel: {list}. Add a forecast channel to each division first."_ |
| Signup module not configured | _"Signup module not configured — run `/signup config` first."_ |
| Bot lacks channel permissions | _"Bot is missing `manage_channels` permission on <#channel>."_ |
| Phase catch-up failure | _"Weather module enable failed during phase execution: {reason}. Module remains disabled."_ |

---

## `/module disable <module_name>`

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `module_name` | `Choice[str]` | Yes | `"weather"` or `"signup"` |

### Preconditions

- Server config exists.
- Interaction originates from the configured interaction channel.
- Caller has `MANAGE_GUILD` permission.
- Module is not already disabled (idempotency guard).

### Behaviour

#### Weather disable
1. Call `SchedulerService.cancel_all_weather_for_server(server_id)` — cancels all `phase*`, `mystery_*`, `cleanup_*` jobs for all rounds of all seasons owned by this server.
2. Mark `server_configs.weather_module_enabled = 0`.
3. Reply ephemeral: _"✅ Weather module disabled. All scheduled weather jobs have been cancelled."_

#### Signup disable
1. If `signup_module_config.signups_open == True`: force-close signups (same logic as `/signup disable`):
   - Delete signup button message (graceful `NotFound`).
   - Reset `selected_tracks_json = '[]'`, `signups_open = 0`, `signup_button_message_id = NULL`.
   - Transition all drivers in active season with state `PENDING_SIGNUP_COMPLETION` or `PENDING_DRIVER_CORRECTION` to `NOT_SIGNED_UP`.
2. Remove Discord channel permission overwrites from `signup_channel_id`.
3. Delete `signup_module_config`, `signup_module_settings`, `signup_availability_slots` rows for this server.
4. Mark `server_configs.signup_module_enabled = 0`.
5. Reply ephemeral: _"✅ Signup module disabled. All signup configuration has been cleared."_

### Error Responses (ephemeral)

| Condition | Message |
|-----------|---------|
| Module already disabled | _"Weather / Signup module is already disabled."_ |

---

## Audit Trail

Both enable and disable commands emit an `AuditEntry` with:
- `action`: `"MODULE_ENABLE"` / `"MODULE_DISABLE"`
- `details`: `{"module": "weather" | "signup"}`
- `actor_id`: caller's Discord user ID
