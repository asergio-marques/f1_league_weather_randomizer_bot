-- Migration 002: Add test_mode_active flag to server_configs
-- Allows per-server test mode state to persist across bot restarts.

ALTER TABLE server_configs ADD COLUMN test_mode_active INTEGER NOT NULL DEFAULT 0;
