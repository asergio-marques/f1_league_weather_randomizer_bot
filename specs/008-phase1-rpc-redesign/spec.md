# Feature Specification: Phase 1 Rpc Distribution Redesign

**Feature Branch**: `008-phase1-rpc-redesign`  
**Created**: 2026-03-05  
**Status**: Draft  
**Input**: User description: "Redesign Phase 1 Rpc generation to use a configurable statistical distribution per-track instead of the deterministic Btrack formula"

## Overview

Phase 1 currently computes `Rpc` via a deterministic formula driven by a fixed track base factor (`Btrack`) and two uniform random draws (`rand1`, `rand2` ∈ [1, 98]). This feature replaces that formula with a **per-track configurable statistical distribution**, where each track has an administrator-configurable **mean rain percentage** (`μ_track`) and **dispersion parameter** (`σ_track`). `Rpc` is drawn stochastically from this distribution at Phase 1 trigger time.

The chosen distribution is the **Beta distribution**, parameterised by deriving α and β internally from the user-facing μ and σ values: $\nu = \frac{\mu(1-\mu)}{\sigma^2} - 1$, $\alpha = \mu\nu$, $\beta = (1-\mu)\nu$. The Beta distribution is natively bounded to [0, 1] (no clamping required in normal operation), produces right-skewed draws for low-mean tracks enabling rare but genuine surprise wet events, and allows σ to serve as a transparent per-track chaos knob. The user-visible parameters remain μ (mean rain probability) and σ (dispersion); α/β are implementation details. All downstream phases (Phase 2, Phase 3) and the amendment-invalidation pipeline remain unchanged; only the `Rpc` production mechanism in Phase 1 is affected.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Draw Rpc from configured distribution (Priority: P1)

At T−5 days, the bot draws `Rpc` for a round from the per-track statistical distribution (parameterised by `μ_track` and `σ_track`) and posts the Phase 1 forecast message, replacing the old `(Btrack * rand1 * rand2) / 3.025` formula entirely.

**Why this priority**: This is the core mechanical change. Without it no other story is testable.

**Independent Test**: Trigger Phase 1 against a seeded test environment for a single round; verify that `Rpc` ∈ [0, 1] was drawn according to the configured parameters, and that the forecast message and calculation log entry are both produced correctly.

**Acceptance Scenarios**:

1. **Given** a round with track = United Kingdom (`μ`=0.30, `σ`=0.05), **When** Phase 1 fires at T−5d, **Then** the drawn `Rpc` ∈ [0.0, 1.0], the calc-log records: track, μ, σ, distribution type, raw draw, clamped `Rpc`, UTC timestamp, and the Phase 1 message is posted to the division weather channel.
2. **Given** a distribution draw produces a value outside [0, 1], **When** Phase 1 fires, **Then** `Rpc` is clamped to [0.0, 1.0]; the log records both the raw draw and the clamped value.
3. **Given** Phase 1 has already fired and a round amendment subsequently occurs, **When** amendment invalidation runs, **Then** the previous `Rpc` is marked `INVALIDATED` and a fresh draw is performed using the same distribution logic.

---

### User Story 2 — Server admin configures per-track distribution parameters (Priority: P1)

A config-authority user can update `μ_track` and/or `σ_track` for any track via a bot command at any time — before or after season review approval — without a season reset.

**Why this priority**: Configurable parameters are the headline requirement; defaults without a config command leave the feature incomplete.

**Independent Test**: Issue a track parameter update command; verify the new values are persisted and used by the next Phase 1 draw for that track.

**Acceptance Scenarios**:

1. **Given** a season in `SETUP` state, **When** a config-authority user updates Belgium (`μ`=0.30, `σ`=0.08), **Then** the values are persisted and an ephemeral confirmation is returned.
2. **Given** a season in `ACTIVE` state, **When** the same update is issued, **Then** the values are persisted and an audit log entry records: actor, track, old values, new values, timestamp.
3. **Given** a user without config-authority issues the update command, **Then** the bot rejects it with a clear permission error (ephemeral).
4. **Given** a config-authority user supplies `σ` ≤ 0 or `μ` outside (0.0, 1.0), **Then** the bot rejects the input with a descriptive validation error before persisting anything.

---

### User Story 3 — Default parameter values ship with the bot (Priority: P2)

All tracks ship with pre-populated default `μ_track` and `σ_track` values. A fresh installation with no admin overrides must draw from these defaults without additional setup.

**Why this priority**: Enables out-of-the-box use; required for integration tests to pass against a clean database.

**Independent Test**: Run Phase 1 on a freshly seeded database with no admin overrides; verify the draw uses the default values from the Default Parameter Table.

**Acceptance Scenarios**:

1. **Given** a fresh database (no admin overrides), **When** Phase 1 fires for any track in the Default Parameter Table, **Then** the draw uses that track's default `μ` and `σ`.
2. **Given** an admin has overridden a track's parameters, **When** a reset-to-defaults command is issued for that track, **Then** the server override is removed, the track reverts to the bot-packaged default values, and an audit entry is written recording the actor and the reversion.

---

### Edge Cases

- What happens when the drawn `Rpc` is exactly 0.0 or 1.0? Phase 2 map construction must tolerate boundary values without division-by-zero or empty buckets.
- What happens when `σ_track` is large relative to `μ_track`, causing frequent out-of-range draws? The log must record the raw draw regardless.
- If a track is not present in the bot-packaged default table AND has no server override (e.g., a hypothetical future circuit not yet in the defaults), Phase 1 MUST block: it MUST NOT fire, and MUST post an error to the calculation log channel instructing a config-authority user to set μ and σ for that track before the T−5d window passes.
- If the same track appears in multiple divisions, both divisions use the same `μ_track`/`σ_track` values (server-wide scope). Each division still performs its own independent Phase 1 draw at T−5d, so their drawn `Rpc` values will differ despite sharing the same parameters.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Phase 1 MUST derive `Rpc` by drawing from a per-track statistical distribution parameterised by `μ_track` and `σ_track`, replacing the previous `(Btrack * rand1 * rand2) / 3.025` formula entirely.
- **FR-002**: The distribution MUST produce values clampable to [0.0, 1.0]. Raw draws outside this range MUST be clamped; both raw and clamped values MUST be written to the calculation log.
- **FR-003**: `Rpc` MUST be rounded to two decimal places after clamping, consistent with prior behaviour.
- **FR-004**: The bot MUST ship with immutable, packaged default `μ` and `σ` values for every track in the Default Parameter Table. These are the authoritative fallback values and MUST be present without any admin action or database seeding step.
- **FR-005**: Config-authority users MUST be able to (a) set a server-level override for `μ_track` and/or `σ_track` for any track at any time (SETUP or ACTIVE season state), and (b) reset any track's server override back to the bot-packaged default via a dedicated reset command. Both operations MUST NOT require a season reset.
- **FR-006**: The update command MUST validate: `μ_track` ∈ (0.0, 1.0) exclusive, `σ_track` > 0.0. Invalid inputs MUST be rejected with a descriptive error before any persistence occurs.
- **FR-007**: Every successful update to `μ_track` or `σ_track` MUST produce a timestamped audit log entry (actor, track, old values, new values) per Principle V.
- **FR-008**: The Phase 1 calculation log entry MUST record: track ID, `μ_track`, `σ_track`, distribution type, raw draw, clamped `Rpc`, UTC timestamp.
- **FR-009**: The public Phase 1 forecast message format is unchanged: `"Weather radar information for @<DivisionRole>: the likelihood of rain in the next round in <Track> is <Rpc>%!"` where `<Rpc>` is rounded to the nearest integer percentage.
- **FR-010**: Phase 1 MUST draw `Rpc` from a **Beta distribution**. The implementation MUST derive α and β from the stored μ and σ via: `ν = μ(1−μ)/σ² − 1`, `α = μν`, `β = (1−μ)ν`. The Beta distribution is the sole supported distribution type for this version; per-track distribution-type selection is out of scope.
- **FR-014**: The README MUST document how `μ_track` and `σ_track` interact with the Beta distribution shape — specifically how increasing σ widens the distribution and pushes probability into the tails (with concrete examples), and the J-shaped / humped-bell transition that occurs when α crosses 1. This documentation MUST be delivered as part of this feature.
- **FR-011**: Track parameter configuration MUST have server-wide scope. The effective μ/σ for a track is resolved at Phase 1 draw time: use the server override if one exists; otherwise fall back to the bot-packaged default. A parameter change or reset MUST NOT trigger re-draws of any already-persisted Phase 1 result.
- **FR-015**: If a track scheduled for a round has no bot-packaged default AND no server override, Phase 1 MUST NOT fire for that round. The bot MUST post an error to the calculation log channel identifying the track and instructing a config-authority user to configure μ and σ before the T−5d window expires.
- **FR-012**: The configuration command MUST be accepted only in the configured interaction channel from config-authority role holders, per Principle I.
- **FR-013**: No migration strategy for existing active seasons is required. Deployment is against a clean database (`bot.db` deleted prior to deployment); the schema is created fresh with `μ_track` and `σ_track` present from the outset. The `btrack` column MAY be omitted from the new schema entirely.

### Key Entities

- **Track** (existing entity, fields changed):
  - `mu_rain_pct` (float, nullable): server-level override for mean rain probability; `NULL` means "use bot-packaged default"
  - `sigma_rain_pct` (float, nullable): server-level override for dispersion; `NULL` means "use bot-packaged default"
  - `btrack` (float): OMITTED from the new schema entirely
  - Bot-packaged defaults are resolved in application code (not stored in the DB per-row); they are the values from the Default Parameter Table.

- **PhaseResult / audit log** (existing entity, fields added):
  - `raw_rpc_draw` (float, nullable): pre-clamp draw value (equal to `Rpc` for Beta since no clamping is needed under normal conditions; populated for auditability regardless)
  - `distribution_type` (string): always `"beta"` in this version; stored for forward-compatibility
  - `mu_used` (float): `μ_track` value at moment of draw
  - `sigma_used` (float): `σ_track` value at moment of draw
  - `alpha_used` (float): derived α at moment of draw (for full audit reproducibility)
  - `beta_used` (float): derived β at moment of draw

### Default Parameter Table

| Track          | μ (mean) | σ (stddev) |
|----------------|----------|------------|
| Bahrain        | 5%       | 2%         |
| Saudi Arabia   | 5%       | 3%         |
| Australia      | 10%      | 5%         |
| Japan          | 25%      | 7%         |
| China          | 25%      | 5%         |
| Miami          | 15%      | 7%         |
| Imola          | 25%      | 5%         |
| Monaco         | 25%      | 5%         |
| Canada         | 30%      | 5%         |
| Barcelona      | 20%      | 5%         |
| Madrid         | 15%      | 5%         |
| Austria        | 25%      | 7%         |
| United Kingdom | 30%      | 5%         |
| Hungary        | 25%      | 5%         |
| Belgium        | 30%      | 8%         |
| Netherlands    | 25%      | 5%         |
| Monza          | 15%      | 3%         |
| Azerbaijan     | 10%      | 3%         |
| Singapore      | 20%      | 7%         |
| Texas          | 10%      | 3%         |
| Mexico         | 5%       | 3%         |
| Brazil         | 30%      | 8%         |
| Las Vegas      | 5%       | 2%         |
| Qatar          | 5%       | 2%         |
| Abu Dhabi      | 5%       | 3%         |
| Portugal       | 10%      | 3%         |
| Turkey         | 10%      | 5%         |

---

## Non-Functional / Quality Attributes

- Distribution sampling MUST complete within the same < 3-second acknowledgment window as all other commands (O(1) operation; no meaningful constraint in practice).
- `μ_track` and `σ_track` MUST be persisted to durable storage; in-memory caching is permitted as a read-through layer only.
- Schema changes MUST be delivered as a versioned migration applied automatically on startup.
- The feature MUST NOT alter Phase 2 or Phase 3 computation contracts; `Rpc` remains a float in [0.0, 1.0] passed downstream unchanged.

---

## Clarifications

### Session 2026-03-05

- Q: Which statistical distribution should be used for the Rpc draw — Gaussian, Beta, Truncated Normal, or Log-normal? → A: **Beta distribution**. Naturally bounded to [0, 1]; right-skewed at low μ enabling rare shock wet events; σ is a transparent per-track chaos knob; α/β derived internally from μ/σ. The σ behaviour (spike rarity, J-shape transition when α < 1) MUST be documented in the README.
- Q: What is the scope of μ_track/σ_track configuration — global per-track, per-season, or per-division? → A: **Global per-track (server-wide)**. One set of μ/σ per track, shared across all divisions and all seasons. Changes take effect for future Phase 1 draws only; already-persisted Rpc values are never retroactively recalculated.
- Q: What is the deployment migration strategy for existing active seasons? → A: **No migration needed** — the database (`bot.db`) will be deleted prior to deployment; schema is created fresh with the new columns present from the start. `btrack` column is dropped from the schema entirely.
- Q: How should unknown tracks (no packaged default, no server override) be handled at Phase 1, and is there a reset-to-defaults command? → A: **Two-layer model**: bot ships with immutable packaged defaults for all known tracks; server stores nullable overrides. Effective value = override if set, else packaged default. A reset command (removes override) is **in scope**. For tracks with no packaged default AND no override, Phase 1 MUST block with an error to the calc-log channel.
