# Data Model: Phase 1 Rpc Distribution Redesign

**Branch**: `008-phase1-rpc-redesign` | **Date**: 2026-03-05

---

## Entities Changed / Added

### 1. `track.py` — application-code constants (not DB)

**Before**:
```python
TRACKS: dict[str, float]   # name → btrack (single float)
get_btrack(name) → float
```

**After**:
```python
TRACK_DEFAULTS: dict[str, tuple[float, float]]  # name → (mu_default, sigma_default)
get_default_rpc_params(name: str) → tuple[float, float]
    """Return (mu, sigma) packaged defaults for name; raise ValueError for unknown tracks."""

TRACK_NAMES: Final[list[str]] = list(TRACK_DEFAULTS.keys())
    # Convenience alias used by autocomplete in season_cog / amendment_cog
```

**TRACK_DEFAULTS values** (all values fractional, e.g. 0.05 = 5%):

| Track | μ | σ |
|---|---|---|
| Abu Dhabi | 0.05 | 0.03 |
| Australia | 0.10 | 0.05 |
| Austria | 0.25 | 0.07 |
| Azerbaijan | 0.10 | 0.03 |
| Bahrain | 0.05 | 0.02 |
| Barcelona | 0.20 | 0.05 |
| Belgium | 0.30 | 0.08 |
| Brazil | 0.30 | 0.08 |
| Canada | 0.30 | 0.05 |
| China | 0.25 | 0.05 |
| Hungary | 0.25 | 0.05 |
| Imola | 0.25 | 0.05 |
| Japan | 0.25 | 0.07 |
| Las Vegas | 0.05 | 0.02 |
| Madrid | 0.15 | 0.05 |
| Mexico | 0.05 | 0.03 |
| Miami | 0.15 | 0.07 |
| Monaco | 0.25 | 0.05 |
| Monza | 0.15 | 0.03 |
| Netherlands | 0.25 | 0.05 |
| Portugal | 0.10 | 0.03 |
| Qatar | 0.05 | 0.02 |
| Saudi Arabia | 0.05 | 0.03 |
| Singapore | 0.20 | 0.07 |
| Texas | 0.10 | 0.03 |
| Turkey | 0.10 | 0.05 |
| United Kingdom | 0.30 | 0.05 |

---

### 2. `track_rpc_params` — new DB table (`005_track_rpc_params.sql`)

Stores **server-level override** rows. A track not present in this table uses the
bot-packaged default from `TRACK_DEFAULTS`.

```sql
CREATE TABLE IF NOT EXISTS track_rpc_params (
    track_name      TEXT    PRIMARY KEY,
    mu_rain_pct     REAL    NOT NULL,   -- fractional, e.g. 0.30 = 30%
    sigma_rain_pct  REAL    NOT NULL,   -- fractional, e.g. 0.08 = 8%
    updated_at      TEXT    NOT NULL,   -- ISO UTC datetime of last update
    updated_by      TEXT    NOT NULL    -- Discord display name of last actor
);
```

**Resolution rule** (applied in `track_service.get_effective_rpc_params`):
1. Query `SELECT mu_rain_pct, sigma_rain_pct FROM track_rpc_params WHERE track_name = ?`
2. If a row exists → use override values.
3. If no row → look up `TRACK_DEFAULTS[track_name]`.
4. If track_name not in `TRACK_DEFAULTS` and no row → raise `ValueError` → Phase 1 blocks
   (FR-015).

---

### 3. `phase_results.payload` — expanded Phase 1 JSON blob

**Before** (Phase 1 payload keys):
```json
{
  "phase": 1,
  "round_id": 42,
  "track": "Belgium",
  "btrack": 0.30,
  "rand1": 71,
  "rand2": 44,
  "rpc": 0.29
}
```

**After**:
```json
{
  "phase": 1,
  "round_id": 42,
  "track": "Belgium",
  "distribution": "beta",
  "mu": 0.30,
  "sigma": 0.08,
  "alpha": 9.5625,
  "beta_param": 22.3125,
  "raw_draw": 0.2847,
  "rpc": 0.28
}
```

Notes:
- `btrack`, `rand1`, `rand2` are removed.
- `beta_param` avoids shadowing the Python builtin `beta` if deserialised.
- `raw_draw` is the pre-rounding, pre-clamp value from `random.betavariate`.
- `rpc` is `round(max(0.0, min(1.0, raw_draw)), 2)`.

---

### 4. `audit_entries` — new change_type values (no schema change)

Two new `change_type` string values are written to the existing `audit_entries` table by
`track_service`:

| change_type | Triggered by | old_value | new_value |
|---|---|---|---|
| `TRACK_RPC_CONFIG` | `/track config` | `"mu=X, sigma=Y"` or `"(default)"` | `"mu=A, sigma=B"` |
| `TRACK_RPC_RESET` | `/track reset` | `"mu=X, sigma=Y"` (the override being removed) | `"(default) mu=A, sigma=B"` |

---

## Entities Unchanged

- `rounds` — no changes; `track_name` column continues to be the join key.
- `sessions` — no changes; Phase 2/3 still consume `Rpc` from `phase_results.payload`.
- `forecast_messages` — no changes.
- `server_configs`, `seasons`, `divisions` — no changes.

---

## State Transitions

```
Track config state (per track):
  [no override row]  --/track config-->  [override row present]
  [override row present]  --/track reset-->  [no override row]

Phase 1 draw (at T-5d):
  resolve_params(track_name, db)  -->  (mu, sigma)
       ↓
  compute_rpc_beta(mu, sigma)  -->  (raw_draw, rpc)
       ↓
  INSERT phase_results payload + UPDATE rounds.phase1_done = 1
```

---

## Validation Rules

| Field | Rule |
|---|---|
| `μ_track` (admin input) | Must be in (0.0, 1.0) exclusive. Values ≤ 0 or ≥ 1 are rejected before persistence. |
| `σ_track` (admin input) | Must be > 0.0. Values ≤ 0 are rejected before persistence. |
| `σ_track` (implicit constraint) | Must satisfy σ < √(μ(1−μ)) to keep α > 0 and β > 0. If violated, Phase 1 blocks at draw time with a calc-log error (treated same as FR-015 unknown track). Admins should consult README guidance. |
| `raw_draw` | Returned by `random.betavariate(α, β)` — always in (0, 1) for valid α > 0, β > 0; clamp applied for safety regardless. |
