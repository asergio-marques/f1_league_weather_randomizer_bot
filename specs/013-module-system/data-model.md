# Data Model: Module System (013)

**Feature Branch**: `013-module-system`

---

## 1. Migration: `009_module_system.sql`

```sql
-- ==================================================================
-- 009_module_system.sql
-- Adds module enable/disable flags, signup module configuration,
-- signup module settings, availability time slots, and makes
-- forecast_channel_id on divisions nullable.
-- ==================================================================

PRAGMA foreign_keys = OFF;

-- ── 1. Add module state columns to server_configs ─────────────────
ALTER TABLE server_configs
    ADD COLUMN weather_module_enabled INTEGER NOT NULL DEFAULT 0;
ALTER TABLE server_configs
    ADD COLUMN signup_module_enabled INTEGER NOT NULL DEFAULT 0;

-- ── 2. Signup module configuration ────────────────────────────────
--   Stores structural config: channel, roles, open state, button msg
CREATE TABLE IF NOT EXISTS signup_module_config (
    server_id                   INTEGER PRIMARY KEY
                                    REFERENCES server_configs(server_id)
                                    ON DELETE CASCADE,
    signup_channel_id           INTEGER NOT NULL,
    base_role_id                INTEGER NOT NULL,
    signed_up_role_id           INTEGER NOT NULL,
    signups_open                INTEGER NOT NULL DEFAULT 0,
    signup_button_message_id    INTEGER,                -- nullable; set when signups opened
    selected_tracks_json        TEXT    NOT NULL DEFAULT '[]'
);

-- ── 3. Signup module settings ──────────────────────────────────────
--   Stores feature-flag settings that can be toggled independently
CREATE TABLE IF NOT EXISTS signup_module_settings (
    server_id               INTEGER PRIMARY KEY
                                REFERENCES server_configs(server_id)
                                ON DELETE CASCADE,
    nationality_required    INTEGER NOT NULL DEFAULT 1, -- bool
    time_type               TEXT    NOT NULL DEFAULT 'TIME_TRIAL',
        -- enum: 'TIME_TRIAL' | 'HOTLAP'
    time_image_required     INTEGER NOT NULL DEFAULT 1  -- bool
);

-- ── 4. Availability time slots ─────────────────────────────────────
--   User-visible slot IDs are computed as 1-based rank when ordered
--   by (day_of_week ASC, time_hhmm ASC). Surrogate PK is internal only.
CREATE TABLE IF NOT EXISTS signup_availability_slots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id       INTEGER NOT NULL
                        REFERENCES server_configs(server_id)
                        ON DELETE CASCADE,
    day_of_week     INTEGER NOT NULL,   -- ISO 8601: 1=Mon … 7=Sun
    time_hhmm       TEXT    NOT NULL,   -- 24h HH:MM, e.g. "14:30"
    UNIQUE(server_id, day_of_week, time_hhmm)
);

-- ── 5. Make forecast_channel_id on divisions nullable ─────────────
--   SQLite does not support ALTER COLUMN DROP NOT NULL.
--   Recreate the divisions table with forecast_channel_id nullable.
--
--   Existing data is preserved; existing non-NULL values stay intact.

CREATE TABLE IF NOT EXISTS divisions_new (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id           INTEGER NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    name                TEXT    NOT NULL,
    mention_role_id     INTEGER NOT NULL,
    forecast_channel_id INTEGER,            -- NULL when weather module disabled
    status              TEXT    NOT NULL DEFAULT 'SETUP',
    tier                INTEGER NOT NULL DEFAULT 1
);

INSERT INTO divisions_new
    SELECT id, season_id, name, mention_role_id, forecast_channel_id, status, tier
    FROM divisions;

DROP TABLE divisions;
ALTER TABLE divisions_new RENAME TO divisions;

PRAGMA foreign_keys = ON;
```

---

## 2. Python Model: `ServerModuleConfig` (additive on `ServerConfig`)

The module-enabled flags are columns on `server_configs`, so they belong on the existing
`ServerConfig` dataclass. Add two new fields:

```python
# src/models/server_config.py  (additions to existing dataclass)
@dataclass
class ServerConfig:
    server_id: int
    interaction_role_id: int
    interaction_channel_id: int
    log_channel_id: int
    test_mode_active: bool
    previous_season_number: int
    weather_module_enabled: bool = False   # NEW
    signup_module_enabled: bool = False    # NEW
```

---

## 3. Python Model: `Division` (existing — change one field)

```python
# src/models/division.py  (change forecast_channel_id to optional)
@dataclass
class Division:
    id: int
    season_id: int
    name: str
    mention_role_id: int
    forecast_channel_id: int | None   # was: int  — CHANGED
    status: str
    tier: int
```

---

## 4. Python Models: Signup Module (new file `src/models/signup_module.py`)

```python
from dataclasses import dataclass, field
from typing import Literal

TimeType = Literal["TIME_TRIAL", "HOTLAP"]

@dataclass
class SignupModuleConfig:
    server_id: int
    signup_channel_id: int
    base_role_id: int
    signed_up_role_id: int
    signups_open: bool
    signup_button_message_id: int | None
    selected_tracks: list[str]          # deserialized from selected_tracks_json

@dataclass
class SignupModuleSettings:
    server_id: int
    nationality_required: bool
    time_type: TimeType
    time_image_required: bool

@dataclass
class AvailabilitySlot:
    """
    id            — internal surrogate PK (used for deletion by row)
    server_id     — owning server
    slot_id       — 1-based user-visible rank (computed on read, NOT stored)
    day_of_week   — 1=Mon … 7=Sun
    time_hhmm     — "HH:MM" 24-hour
    display_label — e.g. "Monday 14:30 UTC" (computed on read)
    """
    id: int
    server_id: int
    slot_id: int          # computed, not persisted
    day_of_week: int
    time_hhmm: str
    display_label: str    # computed, not persisted
```

---

## 5. Entity Relationship Summary

```
server_configs (1)
    │ weather_module_enabled (bool)    ← NEW column
    │ signup_module_enabled  (bool)    ← NEW column
    │
    ├──(1:0..1)── signup_module_config      ← NEW table
    │                signup_channel_id
    │                base_role_id
    │                signed_up_role_id
    │                signups_open
    │                signup_button_message_id
    │                selected_tracks_json
    │
    ├──(1:0..1)── signup_module_settings    ← NEW table
    │                nationality_required
    │                time_type
    │                time_image_required
    │
    └──(1:0..*)── signup_availability_slots ← NEW table
                     id (PK, internal)
                     day_of_week
                     time_hhmm
                     UNIQUE(server_id, day_of_week, time_hhmm)

divisions
    └── forecast_channel_id → INTEGER NULL  ← CHANGED from NOT NULL
```

---

## 6. State Machines

### 6.1 Weather Module State

```
DISABLED ──[/module enable weather]──→ ENABLED
ENABLED  ──[/module disable weather]─→ DISABLED
```

**Guards on `enable`**:
- Active season exists with at least one division.
- Every division in the active season has `forecast_channel_id IS NOT NULL`.

**Side-effects of `enable`**:
- Runs any overdue phase jobs for the active season (sequential, synchronous).
- Schedules all future-horizon phase jobs.

**Side-effects of `disable`**:
- Calls `cancel_all_weather_for_server(server_id)`.
- Weather jobs no longer fire; scheduling on `season approve` is skipped.

---

### 6.2 Signup Module State

```
DISABLED ──[/module enable signup]──→ ENABLED
ENABLED  ──[/module disable signup]─→ DISABLED
```

**Guards on `enable`**:
- `signup_module_config` exists for this server (configured channel + roles).
- Server has `MANAGE_CHANNELS` permission on the configured signup channel.

**Side-effects of `enable`**:
- Applies Discord channel permission overwrites to `signup_channel_id`.

**Side-effects of `disable`**:
- If `signups_open`, force-closes signups first (see 6.3).
- Removes Discord channel permission overwrites.
- Deletes `signup_module_config`, `signup_module_settings`, `signup_availability_slots`
  rows for this server.
- Transitions any active-season drivers in `PENDING_SIGNUP_COMPLETION` or
  `PENDING_DRIVER_CORRECTION` to `NOT_SIGNED_UP` (FR-037).

---

### 6.3 Signup Window State

```
CLOSED ──[/signup enable]──────→ OPEN
OPEN   ──[/signup disable]─────→ CLOSED
OPEN   ──[signup module disable]→ CLOSED  (forced)
```

**Guards on `/signup enable`**:
- `signups_open == False`.
- At least one `AvailabilitySlot` configured.
- At least one track ID in `selected_tracks`.

**Side-effects of open**:
- Posts signup button message to `signup_channel_id`.
- Stores `signup_button_message_id`.

**Side-effects of close**:
- Deletes signup button message (graceful on `NotFound`).
- Clears `selected_tracks_json` to `'[]'`.
- Sets `signups_open = False`.
- Sets `signup_button_message_id = NULL`.

---

## 7. Driver State Machine Extensions (FR-037)

New transitions to add to `DriverService`:

| From | To | Trigger |
|------|----|---------|
| `PENDING_SIGNUP_COMPLETION` | `NOT_SIGNED_UP` | `signup disable` (admin force-close) |
| `PENDING_DRIVER_CORRECTION` | `NOT_SIGNED_UP` | `signup disable` (admin force-close) |

These transitions are enforced in Python, not in the DB schema.
