# Data Model: Driver Profiles, Teams & Season Enhancements

**Phase 1 Output** | Feature: `012-driver-profiles-teams` | Date: 2026-03-06

---

## Entity Relationship Overview

```
server_configs  ──< seasons  ──< divisions  ──< team_instances  ──< team_seats
     │                │                │                                  │
     │                │                └──< rounds (existing, unchanged)  │
     │                │                                                    │
     │          (season_number stored on seasons)                          │
     │                                                                     │
     └──< default_teams (server-level seed)                                │
     │                                                                     │
     └──< driver_profiles ──< driver_season_assignments                    │
               │          └──< driver_history_entries                      │
               └───────────────────────────────────────────────────────────┘
                                    (team_seats.driver_profile_id → nullable FK)
```

---

## New Tables

### `driver_profiles`

Stores one row per Discord user per server who has ever initiated signup or been touched
by an admin action.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | INTEGER | PK AUTOINCREMENT | Surrogate key |
| `server_id` | INTEGER | NOT NULL, FK → server_configs | Scope |
| `discord_user_id` | TEXT | NOT NULL | Discord snowflake as text (see research §3) |
| `current_state` | TEXT | NOT NULL DEFAULT 'NOT_SIGNED_UP' | Enum value — see DriverState |
| `former_driver` | INTEGER | NOT NULL DEFAULT 0 | Boolean (0/1) |
| `race_ban_count` | INTEGER | NOT NULL DEFAULT 0 | Cumulative race bans |
| `season_ban_count` | INTEGER | NOT NULL DEFAULT 0 | Cumulative season bans |
| `league_ban_count` | INTEGER | NOT NULL DEFAULT 0 | Cumulative league bans |

**Unique constraint**: `UNIQUE(server_id, discord_user_id)` — one profile per user per server.

**Index**: `idx_driver_profiles_server` ON `(server_id)`.

**Deletion rule** (enforced by DriverService, not DB trigger): When `current_state` transitions
to `NOT_SIGNED_UP` and `former_driver = 0`, the row is deleted in the same transaction.
The DB row therefore either does not exist (treated as NOT_SIGNED_UP) or has a valid state.

---

### `driver_season_assignments`

Links a driver profile to a division within the currently active season.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | INTEGER | PK AUTOINCREMENT | |
| `driver_profile_id` | INTEGER | NOT NULL, FK → driver_profiles(id) | |
| `season_id` | INTEGER | NOT NULL, FK → seasons(id) | |
| `division_id` | INTEGER | NOT NULL, FK → divisions(id) | |
| `current_position` | INTEGER | NOT NULL DEFAULT 0 | Populated by future results feature |
| `current_points` | INTEGER | NOT NULL DEFAULT 0 | Populated by future results feature |
| `points_gap_to_first` | INTEGER | NOT NULL DEFAULT 0 | Populated by future results feature |

**Unique constraint**: `UNIQUE(driver_profile_id, season_id, division_id)`.

---

### `driver_history_entries`

Archives one row per driver per division per completed/cancelled season they participated in.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | INTEGER | PK AUTOINCREMENT | |
| `driver_profile_id` | INTEGER | NOT NULL, FK → driver_profiles(id) | |
| `season_number` | INTEGER | NOT NULL | Stored at archive time |
| `division_name` | TEXT | NOT NULL | Stored at archive time (name may change) |
| `division_tier` | INTEGER | NOT NULL | Stored at archive time |
| `final_position` | INTEGER | NOT NULL DEFAULT 0 | Populated by future results feature |
| `final_points` | INTEGER | NOT NULL DEFAULT 0 | Populated by future results feature |
| `points_gap_to_winner` | INTEGER | NOT NULL DEFAULT 0 | Populated by future results feature |

---

### `default_teams`

Server-level seed list used when a new division is created.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | INTEGER | PK AUTOINCREMENT | |
| `server_id` | INTEGER | NOT NULL, FK → server_configs | |
| `name` | TEXT | NOT NULL | Team name |
| `max_seats` | INTEGER | NOT NULL DEFAULT 2 | -1 = unlimited (Reserve) |
| `is_reserve` | INTEGER | NOT NULL DEFAULT 0 | Boolean — 1 for Reserve only |

**Unique constraint**: `UNIQUE(server_id, name)`.

**Seeded on bot-init**: When `/bot-init` first runs, the 10 default F1 constructor teams
plus Reserve are inserted for that server if no `default_teams` rows exist yet.

**Reserve invariant**: `is_reserve = 1` rows are excluded from all add/modify/remove
operations; `TeamService` enforces this check before any mutation.

---

### `team_instances`

One row per team per division per season — the team as it lives inside a division.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | INTEGER | PK AUTOINCREMENT | |
| `division_id` | INTEGER | NOT NULL, FK → divisions(id) | |
| `name` | TEXT | NOT NULL | Team display name |
| `max_seats` | INTEGER | NOT NULL DEFAULT 2 | -1 = unlimited |
| `is_reserve` | INTEGER | NOT NULL DEFAULT 0 | 1 for Reserve |

**Unique constraint**: `UNIQUE(division_id, name)`.

**Created automatically**: When a division is created (season setup), `SeasonService` copies
each row from `default_teams` for the server into a `team_instances` row for the new division.

---

### `team_seats`

One row per seat per team instance. Initially `driver_profile_id = NULL` (unassigned).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | INTEGER | PK AUTOINCREMENT | |
| `team_instance_id` | INTEGER | NOT NULL, FK → team_instances(id) | |
| `seat_number` | INTEGER | NOT NULL | 1-based per team |
| `driver_profile_id` | INTEGER | NULL, FK → driver_profiles(id) | NULL = unassigned |

**Unique constraint**: `UNIQUE(team_instance_id, seat_number)`.

**Reserve seats**: Created on demand (when a driver is assigned to Reserve) — not pre-created
since Reserve has no fixed seat count. *(Seat assignment is a future feature; this migration
only creates the table structure.)*

---

## Modified Tables

### `server_configs` — new column

```sql
ALTER TABLE server_configs
  ADD COLUMN previous_season_number INTEGER NOT NULL DEFAULT 0;
```

The `previous_season_number` counter is incremented by `SeasonService` on each season
cancellation or completion.

---

### `seasons` — new column

```sql
ALTER TABLE seasons
  ADD COLUMN season_number INTEGER NOT NULL DEFAULT 0;
```

Set to `(server_config.previous_season_number + 1)` at season creation time and never
changed afterwards. This is the value shown in all bot output.

---

### `divisions` — new column

```sql
ALTER TABLE divisions
  ADD COLUMN tier INTEGER NOT NULL DEFAULT 0;
```

`DEFAULT 0` ensures existing rows remain valid (pre-feature seasons are grandfathered at
tier 0, which will never satisfy the sequential gate for new seasons). A `CHECK` constraint
is not added here to avoid breaking existing rows; validation is enforced in `SeasonService`
and in `DriverCog` at command time.

**Unique constraint on new seasons**: Enforced at the service layer, not as a DB constraint,
to allow the `DEFAULT 0` migration without conflicting on existing rows.

---

## Python Dataclasses

### `DriverState` (enum, new — `src/models/driver_profile.py`)

```python
class DriverState(str, Enum):
    NOT_SIGNED_UP              = "NOT_SIGNED_UP"
    PENDING_SIGNUP_COMPLETION  = "PENDING_SIGNUP_COMPLETION"
    PENDING_ADMIN_APPROVAL     = "PENDING_ADMIN_APPROVAL"
    PENDING_DRIVER_CORRECTION  = "PENDING_DRIVER_CORRECTION"
    UNASSIGNED                 = "UNASSIGNED"
    ASSIGNED                   = "ASSIGNED"
    SEASON_BANNED              = "SEASON_BANNED"
    LEAGUE_BANNED              = "LEAGUE_BANNED"
```

### `DriverProfile` (dataclass, new — `src/models/driver_profile.py`)

```python
@dataclass
class DriverProfile:
    id: int
    server_id: int
    discord_user_id: str
    current_state: DriverState
    former_driver: bool
    race_ban_count: int
    season_ban_count: int
    league_ban_count: int
```

### `DriverSeasonAssignment` (dataclass, new — `src/models/driver_profile.py`)

```python
@dataclass
class DriverSeasonAssignment:
    id: int
    driver_profile_id: int
    season_id: int
    division_id: int
    current_position: int
    current_points: int
    points_gap_to_first: int
```

### `DriverHistoryEntry` (dataclass, new — `src/models/driver_profile.py`)

```python
@dataclass
class DriverHistoryEntry:
    id: int
    driver_profile_id: int
    season_number: int
    division_name: str
    division_tier: int
    final_position: int
    final_points: int
    points_gap_to_winner: int
```

### `DefaultTeam` (dataclass, new — `src/models/team.py`)

```python
@dataclass
class DefaultTeam:
    id: int
    server_id: int
    name: str
    max_seats: int   # -1 = unlimited
    is_reserve: bool
```

### `TeamInstance` (dataclass, new — `src/models/team.py`)

```python
@dataclass
class TeamInstance:
    id: int
    division_id: int
    name: str
    max_seats: int   # -1 = unlimited
    is_reserve: bool
```

### `TeamSeat` (dataclass, new — `src/models/team.py`)

```python
@dataclass
class TeamSeat:
    id: int
    team_instance_id: int
    seat_number: int
    driver_profile_id: int | None  # None = unassigned
```

### `Division` (modified — `src/models/division.py`)

Gains `tier: int = 0` field.

### `Season` (modified — `src/models/season.py`)

Gains `season_number: int = 0` field.

### `ServerConfig` (modified — `src/models/server_config.py`)

Gains `previous_season_number: int = 0` field.

---

## State Machine Transition Map

```python
# Blocklist-based rows use a "not in" check rather than per-state enumeration.
# ALL_STATES = set(DriverState)

ALLOWED_TRANSITIONS = {
    DriverState.NOT_SIGNED_UP: {
        DriverState.PENDING_SIGNUP_COMPLETION,
        # UNASSIGNED and ASSIGNED added by DriverService only if test_mode_active
    },
    DriverState.PENDING_SIGNUP_COMPLETION: {
        DriverState.PENDING_ADMIN_APPROVAL,
    },
    DriverState.PENDING_ADMIN_APPROVAL: {
        DriverState.UNASSIGNED,
        DriverState.PENDING_DRIVER_CORRECTION,
        DriverState.NOT_SIGNED_UP,
        DriverState.SEASON_BANNED,
        DriverState.LEAGUE_BANNED,
    },
    DriverState.PENDING_DRIVER_CORRECTION: {
        DriverState.PENDING_ADMIN_APPROVAL,
        DriverState.SEASON_BANNED,
        DriverState.LEAGUE_BANNED,
    },
    DriverState.UNASSIGNED: {
        DriverState.ASSIGNED,
        DriverState.SEASON_BANNED,
        DriverState.LEAGUE_BANNED,
    },
    DriverState.ASSIGNED: {
        DriverState.SEASON_BANNED,
        DriverState.LEAGUE_BANNED,
    },
    DriverState.SEASON_BANNED: {
        DriverState.NOT_SIGNED_UP,
        DriverState.LEAGUE_BANNED,
    },
    DriverState.LEAGUE_BANNED: {
        DriverState.NOT_SIGNED_UP,
        # Cannot be SEASON_BANNED; no other transitions.
    },
}
```

---

## Validation Rules

| Rule | Enforced In |
|------|-------------|
| State transition not in allowed map → reject | `DriverService.transition()` |
| `former_driver = True` → profile row not deleted | `DriverService.transition()` |
| Seat reference cleared before profile deletion | `DriverService.transition()` |
| User ID reassignment to existing profile → reject | `DriverService.reassign_user_id()` |
| Default team mutation on Reserve → reject | `TeamService.*` (is_reserve check) |
| Season team mutation on non-SETUP season → reject | `TeamService.season_team_*()` |
| Division tier duplicate within season → reject | `SeasonService.add_division()` |
| Season approval with non-sequential tiers → reject + diagnostic | `SeasonService.approve_season()` |
| `/test-mode set-former-driver` when test_mode_active = False → reject | `TestModeCog` |
