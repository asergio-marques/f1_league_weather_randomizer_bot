# Quickstart: Phase 1 Rpc Distribution Redesign

**Branch**: `008-phase1-rpc-redesign` | **Date**: 2026-03-05

---

## What changed

Phase 1 no longer uses the formula `Rpc = (Btrack × rand1 × rand2) / 3025`.
`Rpc` is now drawn from a **Beta distribution** parameterised by a per-track mean (μ) and
standard deviation (σ). Bot-packaged defaults exist for all 27 circuits. Server admins can
override any track's parameters with `/track config` and revert them with `/track reset`.

---

## Deployment steps

1. **Delete `bot.db`** before starting (clean-DB deployment agreed in spec).
2. Pull / deploy branch `008-phase1-rpc-redesign`.
3. Start the bot — migration `005_track_rpc_params.sql` applies automatically.
4. Verify startup log contains `Applied migration: 005_track_rpc_params`.
5. No other manual setup required — packaged defaults are in application code.

---

## Using the new track config commands

All commands require the config-authority role and must be issued in the configured
interaction channel.

### View effective parameters for a track

```
/track info <track>
```

Returns the effective μ and σ for the track (server override if set; packaged default
otherwise), plus the derived α and β, and an example of the spike-probability table.
Response is ephemeral.

### Override a track's parameters

```
/track config <track> <mean_pct> <stddev_pct>
```

- `<mean_pct>`: mean rain probability as a percentage, e.g. `30` for 30% (must be 0–100
  exclusive).
- `<stddev_pct>`: standard deviation as a percentage, e.g. `8` for 8% (must be > 0).

Example — make Belgium more volatile:
```
/track config Belgium 30 12
```

Response is ephemeral. An audit entry is written to the calculation log channel.

### Reset a track to bot-packaged default

```
/track reset <track>
```

Removes the server override for the track. Future Phase 1 draws for that track revert to
the packaged default μ and σ. An audit entry is written.

---

## How Beta distribution parameters affect behaviour

The **σ (stddev)** value is the primary chaos knob.

### Low σ → tight cluster around μ (predictable)

Belgium default (μ=30%, σ=5%):
- ~68% of draws land between 25%–35%
- P(Rpc ≥ 50%) ≈ 0.2%

### Higher σ → wider tails (more surprise)

Belgium with σ=12%:
- ~68% of draws land between 18%–42%
- P(Rpc ≥ 50%) ≈ 5%
- P(Rpc ≤ 10%) ≈ 4%

### Low μ with default σ → mostly dry, occasional spikes (Bahrain, μ=5%, σ=2%)

- P(Rpc ≥ 10%) ≈ 2%; over a 27-race season expect 0–1 meaningful wet Bahrain weekends.
- Raising σ to 5%: P(Rpc ≥ 10%) rises to ~14% — roughly 3–4 wet Bahrain weekends per season.

### Shape transition: humped bell → J-shape

When `α = μν < 1` (typically when σ is large relative to μ), the distribution becomes
**J-shaped**: most draws cluster near 0 but the tail extends further right. This is
desirable behaviour for genuinely arid tracks where rare rain should be dramatic; it means
"usually dry, occasionally wild". See the README for the full derivation and a worked
example.

---

## Phase 1 payload changes

The calculation log now shows:

```
Phase 1 | Round #3 | Belgium (2026-04-15T18:00:00Z)
  distribution : beta
  μ (mean)     : 0.30
  σ (stddev)   : 0.08
  α            : 9.5625
  β            : 22.3125
  raw_draw     : 0.2847
  Rpc          : 0.28  (28%)
```

Previously logged fields `btrack`, `rand1`, `rand2` are no longer present.

---

## Testing after deployment

1. Use `/test-mode enable` and `/test-mode advance` on a round assigned to a known track.
2. Check the calculation log channel — confirm the Phase 1 entry shows `distribution: beta`
   and `raw_draw` and `rpc` fields.
3. Run `/track config <track> <mean> <stddev>` and `/test-mode advance` again on a new
   round — confirm the log uses the updated μ/σ.
4. Run `/track reset <track>` and verify the next draw reverts to packaged defaults.

---

## Running unit tests

```bash
pytest tests/unit/test_math_utils.py   # compute_rpc_beta coverage
pytest tests/unit/test_track_service.py   # override CRUD + audit
pytest tests/unit/ -q   # full unit suite
```
