"""Unit tests for track_service — per-track Beta parameter override CRUD."""

from __future__ import annotations

import json
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# ---------------------------------------------------------------------------
# Fixtures — in-memory aiosqlite database
# ---------------------------------------------------------------------------

@pytest.fixture
async def db():
    """An in-memory aiosqlite DB with the track_rpc_params and audit_entries tables."""
    import aiosqlite
    async with aiosqlite.connect(":memory:") as connection:
        connection.row_factory = aiosqlite.Row
        await connection.execute(
            """
            CREATE TABLE track_rpc_params (
                track_name      TEXT PRIMARY KEY,
                mu_rain_pct     REAL NOT NULL,
                sigma_rain_pct  REAL NOT NULL,
                updated_at      TEXT NOT NULL,
                updated_by      TEXT NOT NULL
            )
            """
        )
        await connection.execute(
            """
            CREATE TABLE audit_entries (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id   INTEGER NOT NULL,
                actor_id    INTEGER NOT NULL,
                actor_name  TEXT    NOT NULL,
                division_id INTEGER,
                change_type TEXT    NOT NULL,
                old_value   TEXT    NOT NULL,
                new_value   TEXT    NOT NULL,
                timestamp   TEXT    NOT NULL
            )
            """
        )
        await connection.commit()
        yield connection


# ---------------------------------------------------------------------------
# get_track_override
# ---------------------------------------------------------------------------

class TestGetTrackOverride:
    async def test_returns_none_when_no_row(self, db) -> None:
        from services.track_service import get_track_override
        result = await get_track_override(db, "Belgium")
        assert result is None

    async def test_returns_tuple_when_row_exists(self, db) -> None:
        from services.track_service import get_track_override, set_track_override
        await set_track_override(db, 999, "Belgium", 0.30, 0.08, 1, "admin")
        await db.commit()
        result = await get_track_override(db, "Belgium")
        assert result == (0.30, 0.08)


# ---------------------------------------------------------------------------
# set_track_override — validation
# ---------------------------------------------------------------------------

class TestSetTrackOverrideValidation:
    async def test_rejects_mu_zero(self, db) -> None:
        from services.track_service import set_track_override
        with pytest.raises(ValueError, match="μ"):
            await set_track_override(db, 999, "Belgium", 0.0, 0.08, 1, "admin")

    async def test_rejects_mu_one(self, db) -> None:
        from services.track_service import set_track_override
        with pytest.raises(ValueError, match="μ"):
            await set_track_override(db, 999, "Belgium", 1.0, 0.08, 1, "admin")

    async def test_rejects_mu_negative(self, db) -> None:
        from services.track_service import set_track_override
        with pytest.raises(ValueError, match="μ"):
            await set_track_override(db, 999, "Belgium", -0.1, 0.08, 1, "admin")

    async def test_rejects_mu_greater_than_one(self, db) -> None:
        from services.track_service import set_track_override
        with pytest.raises(ValueError, match="μ"):
            await set_track_override(db, 999, "Belgium", 1.5, 0.08, 1, "admin")

    async def test_rejects_sigma_zero(self, db) -> None:
        from services.track_service import set_track_override
        with pytest.raises(ValueError, match="σ"):
            await set_track_override(db, 999, "Belgium", 0.30, 0.0, 1, "admin")

    async def test_rejects_sigma_negative(self, db) -> None:
        from services.track_service import set_track_override
        with pytest.raises(ValueError, match="σ"):
            await set_track_override(db, 999, "Belgium", 0.30, -0.05, 1, "admin")

    async def test_no_write_on_validation_failure(self, db) -> None:
        """Nothing is persisted if validation raises."""
        from services.track_service import set_track_override, get_track_override
        with pytest.raises(ValueError):
            await set_track_override(db, 999, "Belgium", 0.0, 0.08, 1, "admin")
        result = await get_track_override(db, "Belgium")
        assert result is None


# ---------------------------------------------------------------------------
# set_track_override — persistence and audit
# ---------------------------------------------------------------------------

class TestSetTrackOverridePersistence:
    async def test_persists_override_row(self, db) -> None:
        from services.track_service import set_track_override, get_track_override
        await set_track_override(db, 999, "Belgium", 0.30, 0.08, 42, "TestUser")
        await db.commit()
        result = await get_track_override(db, "Belgium")
        assert result == (0.30, 0.08)

    async def test_upsert_updates_existing_row(self, db) -> None:
        from services.track_service import set_track_override, get_track_override
        await set_track_override(db, 999, "Belgium", 0.30, 0.08, 42, "TestUser")
        await set_track_override(db, 999, "Belgium", 0.35, 0.06, 42, "TestUser")
        await db.commit()
        result = await get_track_override(db, "Belgium")
        assert result == (0.35, 0.06)

    async def test_writes_audit_entry(self, db) -> None:
        from services.track_service import set_track_override
        await set_track_override(db, 999, "Belgium", 0.30, 0.08, 42, "TestUser")
        await db.commit()
        cursor = await db.execute("SELECT * FROM audit_entries")
        rows = await cursor.fetchall()
        assert len(rows) == 1
        entry = rows[0]
        assert entry["change_type"] == "track.rpc_params"
        assert entry["actor_name"] == "TestUser"
        assert entry["server_id"] == 999
        new_val = json.loads(entry["new_value"])
        assert new_val["mu"] == pytest.approx(0.30)
        assert new_val["sigma"] == pytest.approx(0.08)

    async def test_audit_records_old_value_on_update(self, db) -> None:
        from services.track_service import set_track_override
        await set_track_override(db, 999, "Belgium", 0.30, 0.08, 42, "TestUser")
        await set_track_override(db, 999, "Belgium", 0.35, 0.06, 42, "TestUser")
        await db.commit()
        cursor = await db.execute("SELECT * FROM audit_entries ORDER BY id")
        rows = await cursor.fetchall()
        assert len(rows) == 2
        old_val = json.loads(rows[1]["old_value"])
        assert old_val["mu"] == pytest.approx(0.30)


# ---------------------------------------------------------------------------
# reset_track_override
# ---------------------------------------------------------------------------

class TestResetTrackOverride:
    async def test_returns_none_when_no_override(self, db) -> None:
        from services.track_service import reset_track_override
        result = await reset_track_override(db, 999, "Belgium", 42, "Admin")
        await db.commit()
        assert result is None

    async def test_removes_override_row(self, db) -> None:
        from services.track_service import set_track_override, reset_track_override, get_track_override
        await set_track_override(db, 999, "Belgium", 0.30, 0.08, 42, "Admin")
        await reset_track_override(db, 999, "Belgium", 42, "Admin")
        await db.commit()
        assert await get_track_override(db, "Belgium") is None

    async def test_returns_old_values_on_reset(self, db) -> None:
        from services.track_service import set_track_override, reset_track_override
        await set_track_override(db, 999, "Belgium", 0.30, 0.08, 42, "Admin")
        old = await reset_track_override(db, 999, "Belgium", 42, "Admin")
        await db.commit()
        assert old == (pytest.approx(0.30), pytest.approx(0.08))

    async def test_writes_audit_entry_on_reset(self, db) -> None:
        from services.track_service import set_track_override, reset_track_override
        await set_track_override(db, 999, "Belgium", 0.30, 0.08, 42, "Admin")
        await db.commit()
        await reset_track_override(db, 999, "Belgium", 42, "Admin")
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM audit_entries WHERE change_type = 'track.rpc_params.reset'"
        )
        rows = await cursor.fetchall()
        assert len(rows) == 1
        entry = rows[0]
        assert entry["new_value"] == "reset_to_default"
        old_val = json.loads(entry["old_value"])
        assert old_val["mu"] == pytest.approx(0.30)
