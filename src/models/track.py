"""Track registry: 27 F1 circuits with Beta distribution parameters (μ, σ).

Each circuit has a bot-packaged default mean rain probability (μ) and dispersion
(σ). Server admins may store overrides in the ``track_rpc_params`` DB table; the
effective parameters are resolved at Phase 1 draw time.

Each circuit also has a short numeric ID in TRACK_IDS for use in Discord
autocomplete (users can type an ID or partial name to filter choices).
"""

from __future__ import annotations

from typing import Final

# Ordered by ID (alphabetical). Used for /round-add and /round-amend autocomplete.
# Key = zero-padded two-digit ID string, Value = canonical track name.
TRACK_IDS: Final[dict[str, str]] = {
    "01": "Abu Dhabi",
    "02": "Australia",
    "03": "Austria",
    "04": "Azerbaijan",
    "05": "Bahrain",
    "06": "Barcelona",
    "07": "Belgium",
    "08": "Brazil",
    "09": "Canada",
    "10": "China",
    "11": "Hungary",
    "12": "Imola",
    "13": "Japan",
    "14": "Las Vegas",
    "15": "Madrid",
    "16": "Mexico",
    "17": "Miami",
    "18": "Monaco",
    "19": "Monza",
    "20": "Netherlands",
    "21": "Portugal",
    "22": "Qatar",
    "23": "Saudi Arabia",
    "24": "Singapore",
    "25": "Texas",
    "26": "Turkey",
    "27": "United Kingdom",
}

# Immutable, bot-packaged default Beta distribution parameters for every known circuit.
# Format: track_name -> (mu_rain_pct, sigma_rain_pct)  — both as fractional probabilities.
# These are never stored in the database; they are the authoritative fallback values.
# Server admins may override these per-track via /track config (stored in track_rpc_params).
TRACK_DEFAULTS: Final[dict[str, tuple[float, float]]] = {
    "Bahrain":        (0.05, 0.02),
    "Saudi Arabia":   (0.05, 0.03),
    "Australia":      (0.10, 0.05),
    "Japan":          (0.25, 0.07),
    "China":          (0.25, 0.05),
    "Miami":          (0.15, 0.07),
    "Imola":          (0.25, 0.05),
    "Monaco":         (0.25, 0.05),
    "Canada":         (0.30, 0.05),
    "Barcelona":      (0.20, 0.05),
    "Madrid":         (0.15, 0.05),
    "Austria":        (0.25, 0.07),
    "United Kingdom": (0.30, 0.05),
    "Hungary":        (0.25, 0.05),
    "Belgium":        (0.30, 0.08),
    "Netherlands":    (0.25, 0.05),
    "Monza":          (0.15, 0.03),
    "Azerbaijan":     (0.10, 0.03),
    "Singapore":      (0.20, 0.07),
    "Texas":          (0.10, 0.03),
    "Mexico":         (0.05, 0.03),
    "Brazil":         (0.30, 0.08),
    "Las Vegas":      (0.05, 0.02),
    "Qatar":          (0.05, 0.02),
    "Abu Dhabi":      (0.05, 0.03),
    "Portugal":       (0.10, 0.03),
    "Turkey":         (0.10, 0.05),
}


def get_default_rpc_params(name: str) -> tuple[float, float]:
    """Return the bot-packaged (mu, sigma) for *name*; raise ValueError for unknown circuits."""
    try:
        return TRACK_DEFAULTS[name]
    except KeyError:
        raise ValueError(
            f"Unknown track {name!r}. Valid options: {sorted(TRACK_DEFAULTS)}"
        ) from None


def get_effective_rpc_params(
    name: str,
    override_mu: float | None,
    override_sigma: float | None,
) -> tuple[float, float]:
    """Resolve effective (mu, sigma) for *name* at Phase 1 draw time.

    Resolution order:
      1. If *override_mu* and *override_sigma* are both non-None, use them.
      2. Otherwise fall back to the bot-packaged default from TRACK_DEFAULTS.
      3. Raise ValueError if the track has no packaged default AND no override.
    """
    if override_mu is not None and override_sigma is not None:
        return (override_mu, override_sigma)
    if name in TRACK_DEFAULTS:
        return TRACK_DEFAULTS[name]
    raise ValueError(
        f"Track {name!r} has no packaged default and no server override. "
        "A config-authority user must run /track config before Phase 1 can fire."
    )
