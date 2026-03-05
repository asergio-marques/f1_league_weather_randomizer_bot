# Research: Phase 1 Rpc Distribution Redesign

**Branch**: `008-phase1-rpc-redesign` | **Date**: 2026-03-05

---

## Decision 1 — Distribution type for Rpc

**Decision**: Beta distribution

**Rationale**:
- Natively bounded to (0, 1) — Rpc is always valid with zero clamping risk under normal
  conditions (σ within the feasible region).
- Right-skewed at low μ (e.g., Bahrain, Las Vegas): draws cluster near 0 with an extended
  right tail, enabling rare-but-genuine wet events without the distribution centring on a
  high middle value. This directly addresses the "too few rainy races" concern.
- Symmetric bell-shaped near μ = 0.5 (high-rain tracks), giving natural variability.
- User-facing parameters (μ, σ) map intuitively to mean and spread; α/β are derived
  internally and are invisible to admins.
- `random.betavariate(α, β)` is part of the Python stdlib — zero new dependencies.

**Parameterisation** (derived at call time from stored μ and σ):

```
ν = μ(1 − μ) / σ² − 1
α = μν
β = (1 − μ)ν
```

**Feasibility constraint**: σ must satisfy σ < √(μ(1−μ)); the validation rule σ > 0 plus
the UI documentation are sufficient guards in practice. If an admin supplies a pathological
σ that causes α < 0 or β < 0, Phase 1 MUST detect this at draw time and block with a
calc-log error (same path as FR-015).

**Alternatives considered**:

| Distribution | Reason rejected |
|---|---|
| Gaussian (Normal) | Unbounded — requires hard clamping at [0,1] which distorts the true mean for low-μ tracks; symmetric shape produces no right-tail surprise behaviour |
| Truncated Normal | Bounded by construction but still symmetric — no skew for low-μ tracks; behaviour at boundary is different from interior |
| Log-normal | Right-skewed ✓, but μ/σ control the underlying log-space, not the actual rain probability mean — less intuitive for admins to configure |

---

## Decision 2 — Parameter scope

**Decision**: Global per-track (server-wide), stored as nullable overrides in a new DB
table; bot-packaged defaults live in `track.py` (application code, not DB rows).

**Rationale**:
- Aligns with how `Btrack` worked previously — one value per circuit, no per-season or
  per-division differentiation.
- Clean data model: the `track_rpc_params` table stores only rows where an admin has
  explicitly overridden one or more tracks. If a track has no row, the packaged default is
  used. This avoids seeding 27 rows on every fresh installation.
- Phase 1 resolution logic: `get_effective_rpc_params(track_name, db_path)` → checks DB
  override first, falls back to `TRACK_DEFAULTS[track_name]`.

**Alternatives considered**:

| Scope | Reason rejected |
|---|---|
| Per-season override | Added complexity (extra JOIN in Phase 1 lookup); no demonstrated need — the whole point is a global tuning knob |
| Per-division override | Most granular but unnecessary; same-track divisions would need duplicate config |

---

## Decision 3 — Sampling implementation

**Decision**: `random.betavariate(α, β)` from Python stdlib `random` module.

**Rationale**:
- Identical module already used for `random.randint` in Phase 1, Phase 2, Phase 3.
- Zero new pip dependencies; wheels, Docker layers, and Heroku/Railway slugs stay identical.
- CPython uses the Johnk/Cheng algorithm internally — O(1), accurate, well-tested.

**Alternative**: `scipy.stats.beta.rvs(α, β)` — rejected (new runtime dependency for a
single one-liner; adds ~50 MB to install footprint).

---

## Decision 4 — `compute_rpc` function signature change

**Decision**: Replace `compute_rpc(btrack, rand1, rand2) → float` with
`compute_rpc_beta(mu, sigma) → tuple[float, float]` returning `(raw_draw, rpc)`.

**Rationale**:
- Raw draw must be separately logged for auditability (FR-002, FR-008). Returning both
  means `phase1_service` never has to recompute.
- Clean break from old signature avoids ambiguity; old function can be removed (as
  `test_math_utils.py` is updated) since the only caller (`phase1_service.py`) is rewritten.
- `round(raw, 2)` and `max(0.0, min(1.0, ...))` clamping applied to raw_draw → rpc as
  before, for consistency with downstream (Phase 2 expects 2 dp float).

---

## Decision 5 — `track.py` restructuring

**Decision**: Replace `TRACKS: dict[str, float]` (name → btrack) with
`TRACK_DEFAULTS: dict[str, tuple[float, float]]` (name → (μ, σ)). Keep `TRACK_IDS`
unchanged. Replace `get_btrack` with `get_default_rpc_params(name) → tuple[float, float]`.

**Rationale**:
- `TRACKS` is imported in `season_cog.py` and `amendment_cog.py` only for the set of valid
  track names (autocomplete and validity checks). Both importers are updated to reference
  `TRACK_DEFAULTS` with minimal change (`if name in TRACK_DEFAULTS` etc.).
- Keeping the same module avoids deeper import chain refactors.
- `get_btrack` can be deleted; its single caller (`phase1_service.py`) is rewritten.

---

## Decision 6 — `/track` command location

**Decision**: New `TrackCog` in `src/cogs/track_cog.py`, registered via `bot.py`.

**Rationale**:
- Follows the project's existing one-domain-per-cog convention (season_cog, amendment_cog,
  reset_cog, test_mode_cog).
- Track parameter configuration is an independent domain unrelated to round amendments or
  season setup, so a dedicated cog avoids bloating amendment_cog.

---

## Decision 7 — Audit entries for track config changes

**Decision**: Write to the existing `audit_entries` table (same table used by
`AmendmentService`), using `change_type = "TRACK_RPC_CONFIG"` or `"TRACK_RPC_RESET"`.

**Rationale**: Reuses existing infrastructure; keeps all config mutations in a single audit
table per Principle V. No new table needed.
