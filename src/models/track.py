"""Track registry: 27 F1 circuits with their base rain-probability factor (Btrack).

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

TRACKS: Final[dict[str, float]] = {
    "Bahrain": 0.05,
    "Saudi Arabia": 0.05,
    "Australia": 0.10,
    "Japan": 0.25,
    "China": 0.25,
    "Miami": 0.15,
    "Imola": 0.25,
    "Monaco": 0.25,
    "Canada": 0.30,
    "Barcelona": 0.20,
    "Madrid": 0.15,
    "Austria": 0.25,
    "United Kingdom": 0.30,
    "Hungary": 0.25,
    "Belgium": 0.30,
    "Netherlands": 0.25,
    "Monza": 0.15,
    "Azerbaijan": 0.10,
    "Singapore": 0.20,
    "Texas": 0.10,
    "Mexico": 0.05,
    "Brazil": 0.30,
    "Las Vegas": 0.05,
    "Qatar": 0.05,
    "Abu Dhabi": 0.05,
    "Portugal": 0.10,
    "Turkey": 0.10,
}


def get_btrack(name: str) -> float:
    """Return Btrack for *name*; raise ValueError for unknown circuits."""
    try:
        return TRACKS[name]
    except KeyError:
        raise ValueError(
            f"Unknown track {name!r}. Valid options: {sorted(TRACKS)}"
        ) from None
