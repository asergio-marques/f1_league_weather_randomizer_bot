# Bug Fix Specification: Rpc Formula Divisor & Phase 1 Message Label

**Feature Branch**: `001-fix-rpc-formula`
**Created**: 2026-03-04
**Status**: Draft
**Input**: User-reported: Phase 1 rain probability always outputs 100%; Phase 1 message displays internal label "(Rpc)" that should not be visible to users.

## User Scenarios & Testing *(mandatory)*

### Bug 1 — Phase 1 rain probability always 100% (Priority: P1)

An admin sets up a round and triggers Phase 1. The bot posts the Phase 1 forecast with a rain probability of 100% regardless of the track base probability or the random dice values drawn. The root cause is a wrong divisor in the `compute_rpc` formula: the code divides by `3.025` when the specification requires dividing by `3025`. This makes the result ~1000× too large, causing it to always be clamped to 1.0.

**Why this priority**: The probability value is the core output of Phase 1 and drives the entire Phase 2 slot distribution and Phase 3 weather selection. An always-100% value makes every race forecast deterministically rainy and renders the randomizer completely non-functional.

**Independent Test**: Trigger Phase 1 for any round whose track has a `Btrack` value less than 1.0 (all normal tracks). Observe the logged `rpc` value and the posted Discord message. With the fix applied the logged value must match `round(Btrack * Rand1 * Rand2 / 3025, 2)` and must be less than 1.0 for any typical dice roll.

**Acceptance Scenarios**:

1. **Given** `Btrack = 0.25`, `Rand1 = 79`, `Rand2 = 4`, **When** Phase 1 runs, **Then** `Rpc = round(0.25 * 79 * 4 / 3025, 2) = 0.03` (not 1.0).
2. **Given** the maximum inputs `Btrack = 0.3`, `Rand1 = 98`, `Rand2 = 98`, **When** Phase 1 runs, **Then** `Rpc = round(0.3 * 98 * 98 / 3025, 2) = 0.95` (not 1.0; maximum possible value is 0.96 per specification).
3. **Given** any valid inputs, **When** Phase 1 runs, **Then** the logged `rpc` value matches `round(Btrack * Rand1 * Rand2 / 3025, 2)` clamped to [0.0, 1.0].

---

### Bug 2 — Phase 1 message shows internal label "(Rpc)" (Priority: P2)

The Phase 1 Discord forecast message currently reads `**Rain Probability (Rpc)**: X%`. The `(Rpc)` portion is an internal specification notation that should not appear in user-facing output.

**Why this priority**: This is a presentation-only defect with no correctness impact. It is ranked P2 only because Bug 1 must be fixed first to produce meaningful probability values; however both fixes are in the same deployment.

**Independent Test**: Trigger Phase 1 for any round. Inspect the Discord message posted to the forecast channel. The line must read `**Rain Probability**: X%` with no `(Rpc)` text.

**Acceptance Scenarios**:

1. **Given** Phase 1 runs successfully, **When** the forecast message is posted, **Then** the rain probability line reads `**Rain Probability**: X%` with no parenthetical notation.
2. **Given** Phase 1 runs successfully, **When** the forecast message is posted, **Then** all other message content (role mention, track name, follow-up note) is unchanged.

---

### Edge Cases

- What if `Btrack * Rand1 * Rand2 / 3025` produces a value outside [0.0, 1.0]? → Clamping logic already exists and must remain; with the correct divisor this should only trigger for malformed input data.
- Does the divisor change affect Phase 2 or Phase 3 outputs? → No. Both phases consume the already-computed `rpc` float stored in `PhaseResult.payload`; the formula change only affects how that float is computed in Phase 1.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `compute_rpc(btrack, rand1, rand2)` in `src/utils/math_utils.py` MUST divide by `3025` (integer), not `3.025`.
- **FR-002**: The docstring of `compute_rpc` MUST be updated to reflect the correct divisor.
- **FR-003**: The Phase 1 forecast message produced by `phase1_message()` in `src/utils/message_builder.py` MUST display `**Rain Probability**:` with no `(Rpc)` suffix.
- **FR-004**: All existing unit tests for `compute_rpc` MUST be updated to assert the correct output values under the new divisor. Any test that previously expected a clamped value of 1.0 due to the wrong divisor MUST be corrected.

### Key Entities

- **`compute_rpc(btrack, rand1, rand2) -> float`**: Pure function in `src/utils/math_utils.py`. Formula: `round(btrack * rand1 * rand2 / 3025, 2)`, result clamped to [0.0, 1.0].
- **`phase1_message(division_role_id, track, rpc_pct) -> str`**: Message builder in `src/utils/message_builder.py`. Affected line: the `Rain Probability` label.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For the observed production values (`Btrack=0.25`, `Rand1=79`, `Rand2=4`), `compute_rpc` returns `0.03`, not `1.0`.
- **SC-002**: The maximum possible `Rpc` value (`Btrack=0.3`, `Rand1=98`, `Rand2=98`) returns `0.95` (≤ 0.96 as stated in specification), not `1.0`.
- **SC-003**: The Phase 1 Discord message contains the string `**Rain Probability**:` and does not contain the string `(Rpc)`.
- **SC-004**: All existing unit tests pass after the fix (no regressions).

---

## Clarifications

*None required — root cause and fix are both unambiguous from the production log and the specification formula.*
