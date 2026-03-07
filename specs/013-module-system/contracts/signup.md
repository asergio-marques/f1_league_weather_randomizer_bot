# Command Contract: `/signup` Group

**Feature**: 013-module-system  
**Cog**: `src/cogs/signup_cog.py`  
**Access Tiers**:
- Config/settings commands: Server Admin (`@channel_guard @admin_only`)
- Slot and open/close commands: Trusted (`@channel_guard @admin_only` — same tier per research §7)

---

## Command Tree

```
/signup
├── config
│   ├── channel   <channel>
│   ├── roles     <base_role> <signed_up_role>
│   └── view
├── nationality   toggle
├── time-type     toggle
├── time-image    toggle
├── time-slot
│   ├── add       <day> <time>
│   ├── remove    <slot_id>
│   └── list
├── enable        [<track_ids>...]
└── disable
```

All commands in this group require the signup module to be enabled
(checked in cog's global `interaction_check`), EXCEPT `config channel`,
`config roles`, and `config view` which operate on configuration that
must exist BEFORE enabling.

---

## `/signup config channel <channel>`

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `channel` | `discord.TextChannel` | Yes | Channel for signup interactions |

### Behaviour
1. Validate bot has `send_messages` + `manage_channels` permissions on the channel.
2. Upsert `signup_module_config` row with `signup_channel_id = channel.id`. Create
   the row if it does not exist (with `base_role_id = 0`, `signed_up_role_id = 0`
   as sentinel values until roles are configured).
3. Reply ephemeral: _"✅ Signup channel set to <#channel>."_

### Error Responses

| Condition | Message |
|-----------|---------|
| Bot lacks permissions on channel | _"Bot is missing required permissions on <#channel>."_ |

---

## `/signup config roles <base_role> <signed_up_role>`

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `base_role` | `discord.Role` | Yes | Role granted to all server members who may sign up |
| `signed_up_role` | `discord.Role` | Yes | Role granted on successful signup completion |

### Behaviour
1. Validate both roles belong to the guild.
2. Upsert `signup_module_config.base_role_id` and `signed_up_role_id`.
3. Reply ephemeral: _"✅ Signup roles configured."_

---

## `/signup config view`

Returns a formatted ephemeral embed showing current signup module config:
- Channel: `#<name>` or `Not set`
- Base role: `@<name>` or `Not set`
- Signed-up role: `@<name>` or `Not set`
- Signup settings (nat required, time type, time image required)
- Signups open: `Yes` / `No`

---

## `/signup nationality toggle`

Toggles `signup_module_settings.nationality_required`.  
If no settings row exists, creates it with defaults, then toggles.  
Reply ephemeral: _"✅ Nationality requirement: **ON** / **OFF**."_

### Precondition
- Signup module enabled.

---

## `/signup time-type toggle`

Cycles `signup_module_settings.time_type`:  
`TIME_TRIAL → HOTLAP → TIME_TRIAL → …`  
Reply ephemeral: _"✅ Time type: **Time Trial** / **Hotlap**."_

### Precondition
- Signup module enabled.

---

## `/signup time-image toggle`

Toggles `signup_module_settings.time_image_required`.  
Reply ephemeral: _"✅ Time image requirement: **ON** / **OFF**."_

### Precondition
- Signup module enabled.

---

## `/signup time-slot add <day> <time>`

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `day` | `Choice[str]` | Yes | Day of week (choices: `Monday`…`Sunday`) |
| `time` | `str` | Yes | Time in 12h (`14:30`, `2:30pm`) or 24h (`14:30`) format |

### Behaviour
1. Parse `time` to canonical HH:MM 24-hour. Error if unparseable.
2. Translate `day` choice to ISO weekday integer (1–7).
3. Guard: signups must be closed. If open, error:
   _"Slots cannot be modified while signups are open. Close signups first with `/signup disable`."_
4. Guard: max 25 slots per server. If at limit, error:
   _"Maximum of 25 time slots reached."_
5. INSERT into `signup_availability_slots` (server_id, day_of_week, time_hhmm).
   UNIQUE constraint prevents duplicates — on conflict error:
   _"That slot already exists."_
6. Re-query all slots ordered by (day_of_week ASC, time_hhmm ASC); return 1-based
   user-visible IDs.
7. Reply ephemeral with updated slot list (see `/signup time-slot list` format).

### Error Responses

| Condition | Message |
|-----------|---------|
| Signups open | _"Slots cannot be modified while signups are open."_ |
| Duplicate slot | _"That time slot already exists."_ |
| Unparseable time | _"Could not parse time '{input}'. Use HH:MM 24h or 12h with am/pm."_ |
| Max slots | _"Maximum of 25 time slots reached."_ |

---

## `/signup time-slot remove <slot_id>`

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `slot_id` | `int` | Yes | 1-based user-visible slot ID from `/signup time-slot list` |

### Behaviour
1. Guard: signups must be closed.
2. Fetch all slots for server ordered by (day_of_week ASC, time_hhmm ASC).
3. Map `slot_id` to the corresponding row's surrogate PK (1-based index).
4. If `slot_id` out of range: error _"Slot #{slot_id} does not exist."_
5. DELETE the row by surrogate PK.
6. Reply ephemeral with updated slot list (or "No slots configured." if empty).

---

## `/signup time-slot list`

Returns ephemeral embed with all configured time slots:

```
Availability Time Slots
#1 — Monday 14:30 UTC
#2 — Monday 20:00 UTC
#3 — Wednesday 19:00 UTC
```

If no slots: _"No availability slots configured."_

---

## `/signup enable [<track_ids>]`

Opens the signup window. Posts the signup button to the signup channel.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `track_ids` | `str` (space-separated) | No | Track IDs for the open window. If omitted, the track selection step is skipped (single-track signup or open for any). At least one required if settings require a track selection (see FR-028). |

### Preconditions
- `signups_open == False`.
- At least one `AvailabilitySlot` configured.
- If `track_ids` provided: each must be a valid track ID in the database.

### Behaviour
1. Parse and validate `track_ids`.
2. Store as JSON in `signup_module_config.selected_tracks_json`.
3. Post signup button message to `signup_channel_id`.
4. Store `signup_button_message_id`.
5. Set `signups_open = 1`.
6. Reply ephemeral: _"✅ Signups opened. Button posted in <#channel>."_

### Error Responses

| Condition | Message |
|-----------|---------|
| Signups already open | _"Signups are already open."_ |
| No slots configured | _"At least one availability time slot must be configured before opening signups."_ |
| Invalid track ID | _"Unknown track ID '{id}'."_ |

---

## `/signup disable`

Closes the signup window.

### Preconditions
- `signups_open == True`.

### Behaviour
1. Fetch and delete `signup_button_message_id` from the signup channel (graceful `NotFound`).
2. Reset `selected_tracks_json = '[]'`, `signups_open = 0`, `signup_button_message_id = NULL`.
3. If active season: transition all `PENDING_SIGNUP_COMPLETION` and `PENDING_DRIVER_CORRECTION`
   drivers for this server to `NOT_SIGNED_UP`.
4. Reply ephemeral: _"✅ Signups closed."_

### Error Responses

| Condition | Message |
|-----------|---------|
| Signups already closed | _"Signups are not currently open."_ |

---

## Audit Trail

The following signup commands emit `AuditEntry` records:

| Command | Action |
|---------|--------|
| `/signup enable` | `"SIGNUP_OPEN"` |
| `/signup disable` | `"SIGNUP_CLOSE"` |
| `/module disable signup` (forced close) | `"SIGNUP_FORCE_CLOSE"` |
