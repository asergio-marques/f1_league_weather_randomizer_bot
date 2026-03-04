# Data Model: Track ID Autocomplete & Division Command Cleanup

**Feature**: 003-track-id-autocomplete  
**Date**: 2026-03-04

---

## Changed Entities

### `Division` (DB table + Python dataclass)

**Change**: Remove `race_day` and `race_time` fields.

| Field | Type | Was | Now |
|-------|------|-----|-----|
| `id` | INTEGER PK | ✅ kept | ✅ kept |
| `season_id` | INTEGER FK | ✅ kept | ✅ kept |
| `name` | TEXT NOT NULL | ✅ kept | ✅ kept |
| `mention_role_id` | INTEGER NOT NULL | ✅ kept | ✅ kept |
| `forecast_channel_id` | INTEGER NOT NULL | ✅ kept | ✅ kept |
| `race_day` | INTEGER NOT NULL | ✅ present | ❌ removed (migration 003) |
| `race_time` | TEXT NOT NULL | ✅ present | ❌ removed (migration 003) |

**Rationale**: Every `Round` row already carries `scheduled_at` (full UTC datetime). The division-level race day/time were a redundant default that no code path used after initial insertion.

**Migration**: `003_remove_division_race_fields.sql`

```sql
ALTER TABLE divisions DROP COLUMN race_day;
ALTER TABLE divisions DROP COLUMN race_time;
```

Applied automatically on next bot startup.

---

### `TRACK_IDS` (new read-only registry — `src/models/track.py`)

A new constant alongside the existing `TRACKS` dict. No DB table required.

| Key (string) | Value (string) |
|-------------|---------------|
| `"01"` | `"Abu Dhabi"` |
| `"02"` | `"Australia"` |
| `"03"` | `"Austria"` |
| `"04"` | `"Azerbaijan"` |
| `"05"` | `"Bahrain"` |
| `"06"` | `"Barcelona"` |
| `"07"` | `"Belgium"` |
| `"08"` | `"Brazil"` |
| `"09"` | `"Canada"` |
| `"10"` | `"China"` |
| `"11"` | `"Hungary"` |
| `"12"` | `"Imola"` |
| `"13"` | `"Japan"` |
| `"14"` | `"Las Vegas"` |
| `"15"` | `"Madrid"` |
| `"16"` | `"Mexico"` |
| `"17"` | `"Miami"` |
| `"18"` | `"Monaco"` |
| `"19"` | `"Monza"` |
| `"20"` | `"Netherlands"` |
| `"21"` | `"Portugal"` |
| `"22"` | `"Qatar"` |
| `"23"` | `"Saudi Arabia"` |
| `"24"` | `"Singapore"` |
| `"25"` | `"Texas"` |
| `"26"` | `"Turkey"` |
| `"27"` | `"United Kingdom"` |

**Ordering**: Alphabetical by canonical name, assigned IDs `01`–`27`.

---

## Unaffected Entities

| Table | Status |
|-------|--------|
| `server_configs` | Unchanged |
| `seasons` | Unchanged |
| `rounds` | Unchanged — `track_name` and `scheduled_at` are the authoritative fields |
| `sessions` | Unchanged |
| `phase_results` | Unchanged |
| `audit_log` | Unchanged |

---

## State Transitions

No new lifecycle states. The `PendingDivision` in-memory dataclass (used during `/season-setup` flow) loses `race_day` and `race_time` fields but otherwise participates in the same `SETUP → ACTIVE` season lifecycle as before.


---

## Addendum — Bot Data Reset Command

No new tables or columns are introduced by this feature. The section below documents which rows are affected by each reset mode.

### Deletion Scope by Mode

| Table | Partial reset (`full=False`) | Full reset (`full=True`) |
|-------|------------------------------|--------------------------|
| `sessions` | Deleted (rounds in scope) | Deleted |
| `phase_results` | Deleted (rounds in scope) | Deleted |
| `rounds` | Deleted (divisions in scope) | Deleted |
| `divisions` | Deleted (seasons in scope) | Deleted |
| `seasons` | Deleted (server_id match) | Deleted |
| `audit_entries` | Deleted (server_id match) | Deleted |
| `server_configs` | **Preserved** | **Deleted** |
| `schema_migrations` | Not touched | Not touched |

### Scoping Queries

Intermediate ID sets are fetched before the transaction opens:

```sql
-- season_ids
SELECT id FROM seasons WHERE server_id = ?;

-- division_ids
SELECT id FROM divisions WHERE season_id IN (<season_ids>);

-- round_ids (also used to cancel APScheduler jobs)
SELECT id FROM rounds WHERE division_id IN (<division_ids>);
```

### Return Value

`reset_server_data()` returns a dict with integer counts:

```python
{
    "seasons_deleted": int,
    "divisions_deleted": int,
    "rounds_deleted": int,
}
```
