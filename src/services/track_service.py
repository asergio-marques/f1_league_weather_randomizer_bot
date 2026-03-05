"""Track distribution parameter service.

Manages server-level overrides for per-track Beta distribution parameters
(mu_rain_pct, sigma_rain_pct) stored in the ``track_rpc_params`` table.

Resolution order at Phase 1 draw time:
  1. Server override row (if present in track_rpc_params)
  2. Bot-packaged default from models.track.TRACK_DEFAULTS
  3. ValueError (blocks Phase 1, prompts admin)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

log = logging.getLogger(__name__)


async def get_track_override(
    db: "aiosqlite.Connection",
    track_name: str,
) -> tuple[float, float] | None:
    """Return the server override (mu, sigma) for *track_name*, or None if not set."""
    cursor = await db.execute(
        "SELECT mu_rain_pct, sigma_rain_pct FROM track_rpc_params WHERE track_name = ?",
        (track_name,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return (row["mu_rain_pct"], row["sigma_rain_pct"])


async def set_track_override(
    db: "aiosqlite.Connection",
    server_id: int,
    track_name: str,
    mu: float,
    sigma: float,
    actor_id: int,
    actor_name: str,
) -> None:
    """Persist a server-level override for *track_name*.

    Validates mu and sigma, reads the current value for audit, UPSERTs the row,
    and writes an audit entry.

    Args:
        db: Open aiosqlite connection (caller owns commit).
        server_id: Discord guild ID.
        track_name: Canonical circuit name.
        mu: Mean rain probability; must satisfy 0.0 < mu < 1.0.
        sigma: Dispersion; must be > 0.0.
        actor_id: Discord user ID issuing the command.
        actor_name: Discord user display name (for the audit record).

    Raises:
        ValueError: If mu or sigma fail validation. Nothing is persisted.
    """
    # --- Validate before any write ---
    if mu <= 0.0 or mu >= 1.0:
        raise ValueError(
            f"μ must be in the open interval (0.0, 1.0); received {mu}."
        )
    if sigma <= 0.0:
        raise ValueError(f"σ must be > 0.0; received {sigma}.")

    now = datetime.now(timezone.utc).isoformat()

    # --- Read old values for audit (may be None if no override yet) ---
    old = await get_track_override(db, track_name)
    old_value_json = json.dumps({"mu": old[0], "sigma": old[1]}) if old else "null"
    new_value_json = json.dumps({"mu": mu, "sigma": sigma})

    # --- UPSERT override row ---
    await db.execute(
        """
        INSERT INTO track_rpc_params (track_name, mu_rain_pct, sigma_rain_pct, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(track_name) DO UPDATE SET
            mu_rain_pct  = excluded.mu_rain_pct,
            sigma_rain_pct = excluded.sigma_rain_pct,
            updated_at   = excluded.updated_at,
            updated_by   = excluded.updated_by
        """,
        (track_name, mu, sigma, now, actor_name),
    )

    # --- Audit entry ---
    await db.execute(
        """
        INSERT INTO audit_entries
            (server_id, actor_id, actor_name, division_id, change_type, old_value, new_value, timestamp)
        VALUES (?, ?, ?, NULL, ?, ?, ?, ?)
        """,
        (
            server_id,
            actor_id,
            actor_name,
            "track.rpc_params",
            old_value_json,
            new_value_json,
            now,
        ),
    )

    log.info(
        "track_service: override set for %r by %r (mu=%s, sigma=%s)",
        track_name, actor_name, mu, sigma,
    )


async def reset_track_override(
    db: "aiosqlite.Connection",
    server_id: int,
    track_name: str,
    actor_id: int,
    actor_name: str,
) -> tuple[float, float] | None:
    """Remove the server-level override for *track_name* (revert to packaged default).

    Returns the old (mu, sigma) override values if one existed, else None.
    Writes an audit entry regardless.
    Args:
        db: Open aiosqlite connection (caller owns commit).
        server_id: Discord guild ID.
        track_name: Canonical circuit name.
        actor_id: Discord user ID issuing the command.
        actor_name: Discord user display name.
    """
    now = datetime.now(timezone.utc).isoformat()

    old = await get_track_override(db, track_name)
    old_value_json = json.dumps({"mu": old[0], "sigma": old[1]}) if old else "null"

    await db.execute(
        "DELETE FROM track_rpc_params WHERE track_name = ?",
        (track_name,),
    )

    await db.execute(
        """
        INSERT INTO audit_entries
            (server_id, actor_id, actor_name, division_id, change_type, old_value, new_value, timestamp)
        VALUES (?, ?, ?, NULL, ?, ?, 'reset_to_default', ?)
        """,
        (
            server_id,
            actor_id,
            actor_name,
            "track.rpc_params.reset",
            old_value_json,
            now,
        ),
    )

    log.info(
        "track_service: override reset for %r by %r (previous=%s)",
        track_name, actor_name, old_value_json,
    )
    return old
