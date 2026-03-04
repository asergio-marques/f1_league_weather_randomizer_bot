# Quickstart: Track ID Autocomplete & Division Command Cleanup

**Feature**: 003-track-id-autocomplete  
**Date**: 2026-03-04

---

## What changed for users

### `/division-add` — fewer parameters

Before:
```
/division-add name:Pro role:@Pro forecast_channel:#pro-weather race_day:6 race_time:18:00
```

After:
```
/division-add name:Pro role:@Pro forecast_channel:#pro-weather
```

Race day and time are now captured per round via `/round-add`'s `scheduled_at` parameter, which is the only scheduling value the bot uses to trigger phases.

---

### `/round-add` — autocomplete track dropdown

Start typing in the `track` field and Discord will show a filtered list:

```
/round-add division_name:Pro round_number:1 format:NORMAL track: [type "27" or "united"]
  → shows: 27 – United Kingdom
```

Selecting an entry fills the field with the canonical name. You can also type a bare number (`"5"`) and the bot resolves it automatically.

---

### `/round-amend` — same track autocomplete

```
/round-amend division_name:Pro round_number:1 track: [type "bah"]
  → shows: 05 – Bahrain
```

---

## Existing database upgrade

When the bot starts after this update, migration `003_remove_division_race_fields.sql` runs automatically and drops the `race_day` and `race_time` columns from the `divisions` table. No manual action required.

Log output will include:

```
[INFO] db.database: Applying migration: 003_remove_division_race_fields.sql
[INFO] db.database: Migration applied: 003_remove_division_race_fields.sql
```

---

## Full season setup flow (updated)

```
1. /bot-init interaction_role:@Role interaction_channel:#channel log_channel:#logs

2. /season-setup start_date:2026-04-01 num_divisions:2

3. /division-add name:Pro   role:@Pro-Role   forecast_channel:#pro-weather
   /division-add name:Am    role:@Am-Role    forecast_channel:#am-weather

4. /round-add division_name:Pro round_number:1 format:NORMAL track:[autocomplete] scheduled_at:2026-04-06T18:00:00
   /round-add division_name:Pro round_number:2 format:SPRINT  track:[autocomplete] scheduled_at:2026-04-20T18:00:00
   /round-add division_name:Am  round_number:1 format:NORMAL track:[autocomplete] scheduled_at:2026-04-07T19:00:00

5. /season-review        ← see the full config; press Approve or Go Back
```

---

## Track ID quick reference

| ID | Track | ID | Track |
|----|-------|----|-------|
| 01 | Abu Dhabi | 15 | Madrid |
| 02 | Australia | 16 | Mexico |
| 03 | Austria | 17 | Miami |
| 04 | Azerbaijan | 18 | Monaco |
| 05 | Bahrain | 19 | Monza |
| 06 | Barcelona | 20 | Netherlands |
| 07 | Belgium | 21 | Portugal |
| 08 | Brazil | 22 | Qatar |
| 09 | Canada | 23 | Saudi Arabia |
| 10 | China | 24 | Singapore |
| 11 | Hungary | 25 | Texas |
| 12 | Imola | 26 | Turkey |
| 13 | Japan | 27 | United Kingdom |
| 14 | Las Vegas | | |


---

## Addendum — Bot Data Reset Command

### `/bot-reset` — Reset Server Data

Available to server members with the **Manage Server** permission. Can be run from **any channel** (not restricted to the bot channel).

#### Partial reset (keep server config)

Deletes all seasons, divisions, rounds, sessions, phase results, and audit entries for this server. The server's bot configuration (channel ID, timezone) is preserved, so the bot remains operational immediately.

```
/bot-reset confirm:CONFIRM
```

Response (ephemeral):
```
✅ Server data reset.
Deleted: 2 season(s), 4 division(s), 48 round(s).
Server config preserved — bot remains active in this channel.
```

#### Full reset (wipe everything)

Additionally deletes the `server_configs` row. Equivalent to factory-resetting the bot for this server. After a full reset you must run `/bot-init` again before any other commands will work.

```
/bot-reset confirm:CONFIRM full:True
```

Response (ephemeral):
```
✅ Server data fully reset.
Deleted: 2 season(s), 4 division(s), 48 round(s).
Server config removed — run /bot-init to re-configure.
```

#### Wrong confirmation string

If `confirm` is anything other than `CONFIRM` (case-sensitive), the command is rejected before any deletion occurs:

```
/bot-reset confirm:yes
```

```
❌ Reset aborted. You must pass confirm:CONFIRM (case-sensitive) to proceed.
```

#### Notes

- All deletions happen in a single atomic transaction — either everything is removed or nothing is.
- APScheduler jobs for affected rounds are cancelled before the DB transaction opens.
- Other servers' data is never affected.
