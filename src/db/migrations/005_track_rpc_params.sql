-- Migration 005: track_rpc_params
-- Adds a server-level override table for per-track Beta distribution parameters.
-- When a row exists for a track, Phase 1 uses its mu/sigma instead of the
-- bot-packaged defaults from models.track.TRACK_DEFAULTS.

CREATE TABLE IF NOT EXISTS track_rpc_params (
    track_name      TEXT    PRIMARY KEY,
    mu_rain_pct     REAL    NOT NULL,
    sigma_rain_pct  REAL    NOT NULL,
    updated_at      TEXT    NOT NULL,
    updated_by      TEXT    NOT NULL
);
