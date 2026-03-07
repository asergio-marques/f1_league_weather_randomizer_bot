# Feature Specification: Driver Profiles, Teams & Season Enhancements

**Feature Branch**: `012-driver-profiles-teams`  
**Created**: 2026-03-06  
**Status**: Draft  
**Input**: User description provided via `/speckit.specify`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Driver Profile State Machine Foundation (Priority: P1)

When a Discord user interacts with the bot for the first time or is managed by an admin, their
participation state is tracked accurately. The system correctly enforces all allowed transitions,
rejects all disallowed ones, auto-deletes non-former-driver profiles on return to *Not Signed Up*,
and retains profiles of former drivers indefinitely — even if they leave the server.

**Why this priority**: All other driver management capability (admin commands, team seat
assignment, historical records, ban tracking) depends on a correctly functioning state machine
and persistent driver profile entity existing in a trustworthy state.

**Independent Test**: Use test-mode commands to exercise each allowed and disallowed transition,
verify the resulting state in bot responses, and confirm auto-deletion behavior by inspecting
whether a profile row exists after a non-former-driver transitions to *Not Signed Up*.

**Acceptance Scenarios**:

1. **Given** a Discord user with no profile, **When** the bot looks up their state, **Then** the
   bot treats them as *Not Signed Up* without raising an error.
2. **Given** test mode is enabled and a driver is *Not Signed Up*, **When** a test-mode advance
   targets *Unassigned*, **Then** the profile is created with state *Unassigned*.
3. **Given** a driver in *Pending Admin Approval*, **When** an admin approves the signup,
   **Then** the driver transitions to *Unassigned*.
4. **Given** a driver in *Pending Admin Approval*, **When** an admin requests a correction,
   **Then** the driver transitions to *Pending Driver Correction*.
5. **Given** a driver in *Pending Driver Correction*, **When** the driver resubmits, **Then**
   the driver transitions back to *Pending Admin Approval*.
6. **Given** a driver in *Pending Admin Approval*, **When** an admin rejects the signup,
   **Then** the driver transitions to *Not Signed Up*.
7. **Given** a driver in *Unassigned*, **When** they are assigned to a team, **Then** the
   driver transitions to *Assigned*.
8. **Given** a driver in any state except *League Banned* and *Season Banned*, **When** an
   admin issues a season ban, **Then** the driver transitions to *Season Banned*.
9. **Given** a driver in any state except *League Banned*, **When** an admin issues a league
   ban, **Then** the driver transitions to *League Banned*.
10. **Given** a driver in *Season Banned*, **When** the ban is lifted, **Then** the driver
    transitions to *Not Signed Up*.
11. **Given** a driver in *League Banned*, **When** the ban is lifted, **Then** the driver
    transitions to *Not Signed Up*.
12. **Given** a driver in *League Banned*, **When** an attempt is made to apply a *Season Banned*
    transition, **Then** the bot rejects the transition with a clear error.
13. **Given** a driver in *Not Signed Up* with `former_driver = false`, **When** transitioning
    to *Not Signed Up* (e.g. rejection from *Pending Admin Approval*), **Then** the profile row
    is deleted automatically as part of the same operation.
14. **Given** a driver in *Not Signed Up* with `former_driver = true`, **When** transitioning
    to *Not Signed Up*, **Then** the profile row is retained.
15. **Given** a driver who has left the Discord server, **When** the bot queries their profile,
    **Then** the profile is still present and valid.
16. **Given** an attempt to execute a state transition not in the approved list, **Then** the
    bot rejects it with a clear error before making any data change.

---

### User Story 2 - Driver User ID Reassignment (Priority: P2)

A server administrator can update the Discord User ID linked to an existing driver profile to
handle situations where a driver switches their Discord account. All profile history, state, and
ban counts are preserved unchanged; the change is fully audited.

**Why this priority**: Account changes happen independently of season activity; this is a
low-frequency but critical administrative action — without it, a driver with history would lose
all records on an account switch.

**Independent Test**: Admin issues a reassign command; attempts to locate the profile by the old
User ID return nothing; attempts by the new User ID return the full profile intact; the audit log
contains the reassignment entry.

**Acceptance Scenarios**:

1. **Given** a driver profile linked to User ID A, **When** an admin reassigns to User ID B,
   **Then** the profile is accessible via User ID B and no longer accessible via User ID A.
2. **Given** the reassignment occurs, **Then** all fields (state, former_driver flag, ban counts,
   season assignments, history) are unchanged on the profile.
3. **Given** the reassignment occurs, **Then** an audit log entry is produced recording the
   actor, the old User ID, the new User ID, and the timestamp.
4. **Given** the target User ID B already has a driver profile, **Then** the bot rejects the
   reassignment and returns a clear error without modifying either profile.
5. **Given** a user who does not hold the server admin (trusted config) role issues the command,
   **Then** the bot rejects it with a permission error.

---

### User Story 3 - Test-Mode Former Driver Flag Override (Priority: P3)

When test mode is enabled, a server administrator can manually set a driver's `former_driver`
flag to `true` or `false`. This allows testing of flag-dependent behaviors (auto-deletion, profile
retention) without requiring real in-round participation.

**Why this priority**: A testing aid with narrow impact; it depends on US1 and does not block
any live operational capability.

**Independent Test**: With test mode on, toggle the flag on a driver; observe that the next
*Not Signed Up* transition either deletes or retains the profile according to the new flag value.
Confirm the command is rejected when test mode is off.

**Acceptance Scenarios**:

1. **Given** test mode is **enabled** and a driver has `former_driver = false`, **When** an admin
   sets it to `true`, **Then** `former_driver` is `true` and a subsequent *Not Signed Up*
   transition retains the profile row.
2. **Given** test mode is **enabled** and a driver has `former_driver = true`, **When** an admin
   sets it to `false`, **Then** `former_driver` is `false` and a subsequent *Not Signed Up*
   transition deletes the profile row.
3. **Given** test mode is **disabled**, **When** any user attempts the flag-override command,
   **Then** the bot rejects it with a clear error.
4. **Given** a user who does not hold the server admin (trusted config) role issues the command
   while test mode is enabled, **Then** the bot rejects it with a permission error.

---

### User Story 4 - Default Team Configuration Management (Priority: P4)

A server administrator can add a new team to, rename/modify, or remove a team from the
server-level default team list. This list seeds newly created divisions. The Reserve team always
exists and may never be modified or removed.

**Why this priority**: Default teams must be configurable before season-level team management
(US5) is meaningful; incorrect defaults propagate to every new division.

**Independent Test**: Admin adds a custom team to defaults; creates a new division; the custom
team is present in that division. Admin then removes the custom team from defaults; creates
another division; the custom team is absent.

**Acceptance Scenarios**:

1. **Given** a server, **When** an admin adds a team named "Custom Team" with 2 seats to the
   default configuration, **Then** "Custom Team" appears in the server default list.
2. **Given** "Custom Team" exists in defaults, **When** an admin renames it to "Custom Team B",
   **Then** the updated name is reflected in the server default list.
3. **Given** a team exists in defaults, **When** an admin removes it, **Then** it no longer
   appears in the server default list.
4. **Given** an admin attempts to modify or remove the Reserve team, **Then** the bot rejects
   the action with a clear error.
5. **Given** updated defaults exist, **When** a new division is created, **Then** the division
   contains one team instance per entry in the current default list, plus Reserve.
6. **Given** a user who does not hold the server admin (trusted config) role issues the command,
   **Then** the bot rejects it with a permission error.

---

### User Story 5 - Season Team Configuration Management (Priority: P5)

A server administrator can add, modify, or remove a configurable team across all divisions of the
current season simultaneously. This operation is restricted to the SETUP lifecycle phase only.
Reserve is always excluded from modifications.

**Why this priority**: Season-specific team overrides must be locked in before season approval;
applying changes to all divisions atomically prevents inconsistent rosters across tiers.

**Independent Test**: Admin modifies a team during SETUP; season review shows the change in all
divisions. Admin attempts the same command during an ACTIVE season; bot rejects with a lifecycle
error.

**Acceptance Scenarios**:

1. **Given** a season in SETUP with 3 divisions, **When** an admin adds team "Extra Team" to the
   season, **Then** all 3 divisions gain "Extra Team" in a single operation.
2. **Given** a season in SETUP, **When** an admin removes a configurable team from the season,
   **Then** all divisions lose that team.
3. **Given** a season in ACTIVE or COMPLETED state, **When** an admin attempts to add, modify, or
   remove a season team, **Then** the bot rejects the action with a lifecycle error.
4. **Given** an admin attempts to modify or remove Reserve via this command, **Then** the bot
   rejects the action with a clear error.
5. **Given** a user who does not hold the server admin (trusted config) role issues the command,
   **Then** the bot rejects it with a permission error.

---

### User Story 6 - Season Counter, Division Tier & Roster Review (Priority: P6)

Seasons surface a human-readable sequential number in all output. Divisions require a tier value
on creation, and the bot enforces that all divisions have sequential (gapless) tiers before a
season can be approved. The existing season review command is extended to show the full team
roster per division.

**Why this priority**: These are correctness and usability improvements to the existing season
lifecycle; they do not block driver management but must be in place before any season using the
new data structures is approved and run.

**Independent Test**: Set up a season with two divisions at tiers 1 and 3 (gap); attempt
approval → blocked. Fix to tiers 1 and 2 → approval succeeds. Review shows team rosters.

**Acceptance Scenarios**:

1. **Given** a server that has never had a season, **When** a new season is created, **Then** all
   bot output for that season displays the number 1.
2. **Given** Season 1 is cancelled or completed, **When** a new season is created, **Then** it
   displays the number 2.
3. **Given** creating a division, **When** no tier value is provided, **Then** the bot rejects
   the command with a clear error explaining that a tier is required.
4. **Given** a season in SETUP with divisions at tiers 1 and 3 (gap at 2), **When** season
   approval is requested, **Then** the bot blocks approval and explicitly identifies the gap.
5. **Given** a season in SETUP with divisions at tiers 1, 2, and 3, **When** season approval is
   requested, **Then** approval proceeds normally.
6. **Given** a season review is requested, **Then** each division lists every team with each seat
   showing either the assigned driver or "unassigned", and any drivers with no seat assignment
   appear in a separate unassigned drivers list; Reserve is always shown.
7. **Given** divisions for a season, **Then** they are always returned and displayed in ascending
   tier order (tier 1 first).

---

### Edge Cases

- A driver eligible for auto-deletion is referenced in a team seat: the seat reference must be
  cleared as part of the same atomic deletion transaction.
- Two admins concurrently attempt to reassign the same driver profile: the second operation must
  either detect the conflict and reject, or operate on the post-first-change state — a stale
  overwrite is not acceptable.
- Season team modification (US5) leaves a division with zero configurable teams: permitted —
  Reserve always remains and the season may still proceed to approval if tier rules are met.
- The `former_driver` flag is forced to `false` via test mode while the driver is in an active
  season assignment: the flag change is logged; the assignment data is unaffected.
- A division's `tier` value is the same as another division's tier in the same season: the bot
  must reject the creation or duplication command and report the collision.
- A season completes or is cancelled while a driver is in *Pending Signup Completion* or
  *Pending Admin Approval*: the driver state is unaffected by season lifecycle changes (the
  profile is server-scoped, not season-scoped).

---

## Requirements *(mandatory)*

### Functional Requirements

#### Driver Profile

- **FR-001**: The system MUST treat any Discord user with no profile row as being in the
  *Not Signed Up* state without creating a row or raising an error.
- **FR-002**: The system MUST enforce the approved state machine transitions; any transition
  not in the approved list MUST be rejected with a clear error, and no data MUST be changed.
- **FR-003**: The system MUST automatically delete a driver's profile row when they transition
  to *Not Signed Up* AND `former_driver` is `false`; this deletion MUST occur in the same
  atomic operation as the state change.
- **FR-004**: The system MUST retain the profile row when a driver transitions to *Not Signed Up*
  AND `former_driver` is `true`.
- **FR-005**: The system MUST retain a driver's profile if they leave the Discord server.
- **FR-006**: The driver profile MUST persist: Discord User ID, current state (enumerated),
  `former_driver` flag (boolean, default `false`), current season assignment records (0..n),
  historical season participation records (0..n), race ban count (integer, default 0), season
  ban count (integer, default 0), league ban count (integer, default 0).
- **FR-007**: A server administrator MUST be able to reassign the Discord User ID of a driver
  profile via a dedicated command; the operation MUST be rejected if the target User ID already
  owns a profile.
- **FR-008**: A User ID reassignment MUST produce an audit log entry recording: actor, old User
  ID, new User ID, and timestamp.
- **FR-009**: When test mode is enabled, a server administrator MUST be able to set the
  `former_driver` flag to `true` or `false` via a dedicated command; this MUST produce an
  audit log entry.
- **FR-010**: The `former_driver` flag-override command MUST be rejected when test mode is
  disabled.
- **FR-011**: When test mode is enabled, the system MUST permit a direct *Not Signed Up* →
  *Unassigned* and *Not Signed Up* → *Assigned* transition via test-mode commands, bypassing
  the normal signup flow.

#### Teams

- **FR-012**: Upon creation of a division, the system MUST automatically create one team
  instance per entry in the current server-level default team list, plus one Reserve team
  instance, for that division.
- **FR-013**: Every division MUST always contain a Reserve team; Reserve MUST NOT be removable,
  renameable, or otherwise mutable by any user command.
- **FR-014**: The Reserve team MUST have an unlimited seat capacity; all configurable teams
  MUST default to 2 seats.
- **FR-015**: A server administrator MUST be able to add a team to, rename/modify, or remove a
  team from the server-level default configuration via a dedicated command; Reserve is excluded
  from all mutations.
- **FR-016**: A server administrator MUST be able to add, rename/modify, or remove a configurable
  team across all divisions of the current season simultaneously via a dedicated command; this
  operation MUST be restricted to the SETUP season lifecycle phase; Reserve is excluded.
- **FR-017**: Any attempt to add, modify, or remove Reserve via any user command MUST be rejected
  with a clear error before any data is changed.
- **FR-018**: The season review output MUST list every team per division, showing each seat's
  assigned driver (or "unassigned"), followed by a separate list of drivers in that division who
  are not assigned to any seat; Reserve MUST always be shown.

#### Season Changes

- **FR-019**: Each server MUST maintain a persistent "previous season number" counter,
  initialized to 0, that increments by 1 on each season cancellation or completion.
- **FR-020**: When a season is created, its display number MUST equal (previous season counter + 1).
- **FR-021**: Division creation (both the add and duplicate commands) MUST require a tier integer
  parameter; the command MUST be rejected if no tier is provided.
- **FR-022**: Season approval MUST be blocked if the set of division tier values does not form a
  gapless integer sequence starting at 1 (e.g., {1, 2, 3} passes; {1, 3} or {2, 3} fails).
- **FR-023**: When season approval is blocked due to a tier gap or missing tier-1, the bot MUST
  clearly identify the problem (e.g., "missing tier 2") so an admin can correct it without
  external guidance.
- **FR-024**: In the database, divisions MUST be stored and returned in ascending tier order
  (tier 1 first, representing the highest-level division).
- **FR-025**: No two divisions within the same season MUST share the same tier value; an attempt
  to create or duplicate a division with a conflicting tier MUST be rejected.

### Key Entities

- **DriverProfile**: A Discord user's persistent league identity within a server. Carries
  discord_user_id, current_state (enum), former_driver flag, and cumulative ban counters.
  Associated with 0..n current season assignment records and 0..n historical participation
  records. Scoped to a single Discord server.

- **DriverSeasonAssignment**: Links a DriverProfile to a specific division and tier within the
  active season. Stores current position, current points tally, and points gap to first place
  (all initially zero; populated by a future results feature).

- **DriverHistoryEntry**: Archives a completed season's outcome for a DriverProfile. Stores
  division name, division tier, season number, final position, final points total, and points
  gap to the eventual winner (all initially zero; populated by a future results feature).

- **DefaultTeam** (server-level): A server-wide template entry defining a team's name and
  default seat count. Always includes a protected Reserve entry. Mutable by server admins
  (except Reserve). Used as the seed when a new division is created.

- **TeamInstance** (per division, per season): A team as it exists within a specific division
  of a specific season. Derived from the default template at division-creation time or from a
  season-level team command. Always includes a Reserve instance.

- **TeamSeat**: One occupiable seat within a TeamInstance. Optionally linked to a DriverProfile.
  Reserve seats are unbounded; configurable team seats default to 2.

- **ServerConfig** (modified): Gains a `previous_season_number` integer field (default 0),
  incremented on each season cancellation or completion.

- **Division** (modified): Gains a `tier` integer field. Unique within a season. Divisions are
  stored and displayed in ascending tier order.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every disallowed state transition attempt is rejected by the bot before any data
  change occurs, 100% of the time, with a message identifying the specific invalid transition.
- **SC-002**: A driver who has ever participated in a round (former_driver = true) cannot have
  their profile deleted under any sequence of admin actions or state transitions.
- **SC-003**: A server administrator can reassign a driver's Discord User ID in a single command
  interaction; the full profile history, state, and ban counts are available under the new ID
  immediately after the operation.
- **SC-004**: A season with non-sequential division tiers cannot be approved; the bot's rejection
  message alone is sufficient for an admin to identify and fix the issue without consulting
  external documentation.
- **SC-005**: Default team configuration changes are reflected in every division created after
  the change, with no manual step required to propagate them.
- **SC-006**: Season team configuration changes during SETUP apply to 100% of the season's
  divisions in a single command; no division is left with the old configuration.
- **SC-007**: The season review output accounts for every driver in the system — each driver
  appears either under a team seat or in the "unassigned" list, with no driver omitted.
- **SC-008**: Each season displays its correct sequential number in all bot output, with the
  counter incrementing correctly on both cancellation and completion.

---

## Assumptions

1. The signup data-collection flow (what fields a driver submits during *Pending Signup
   Completion*) is deferred to a later feature. This spec establishes the data structures,
   state machine rules, admin commands, and team/season changes only. The number of new commands
   is limited to those explicitly marked `<NEW COMMAND>` in the source specification:
   driver User ID reassignment, test-mode `former_driver` override, default team management,
   and season team management.

2. Points, positions, and gap values stored on `DriverSeasonAssignment` and `DriverHistoryEntry`
   are populated by a future race-results feature. This spec creates the storage fields; their
   initial value is zero. No computation or update mechanism is defined here.

3. The *Season Banned* expiry mechanism (auto-transition to *Not Signed Up* after N races equal
   to the season length) is deferred. This spec ensures `season_ban_count` and `race_ban_count`
   fields exist, but the expiry trigger logic is out of scope.

4. Promotion and relegation between division tiers are out of scope. The `tier` field is an
   input identifier that enforces sequential ordering; it does not drive any routing logic.

5. Team seat assignment (linking a specific driver to a specific seat) is a future command.
   This spec creates `TeamSeat` records that appear in season review as "unassigned"; no
   assignment command is added here.

6. "Server administrator" throughout this spec means a user holding the Tier-2 trusted/config
   role as defined in Constitution Principle I — not a Discord server owner. The existing
   `channel_guard` mechanism enforces this.

7. The `duplicate` division command inherits the tier requirement: the admin must supply a new,
   non-conflicting tier for the duplicated division.

8. The approved state-machine transitions that reference "unspecified states" in the source
   description (e.g., transitions out of *Assigned*, *Unassigned* in non-test contexts) are
   explicitly deferred and will be outlined in future change specifications.

---

## Constraints & Boundaries

- New Discord slash commands are limited to the four items marked `<NEW COMMAND>`: driver User
  ID reassignment, test-mode former_driver flag toggle, default team add/modify/remove, and
  season team add/modify/remove.
- The signup wizard (notifications during state transitions, data fields the driver provides)
  is out of scope.
- Team seat assignment to drivers is out of scope; seats are created and shown as "unassigned".
- Race result entry, points calculation, and standings display are out of scope.
- Driver ban expiry (auto-unban after N races) is out of scope.
- Promotion/relegation between division tiers is out of scope.
