-- Migration 006: Expand forecast_messages.phase_number CHECK to include 0 (mystery notice).
--
-- Mystery round notices are posted to the forecast channel but were not tracked in
-- forecast_messages (phase_number 1–3 only). This migration expands the allowed set
-- to include 0, allowing mystery notice messages to be stored and cleaned up when
-- test mode is disabled (flush_pending_deletions).

PRAGMA foreign_keys = OFF;

CREATE TABLE IF NOT EXISTS forecast_messages_new (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id     INTEGER NOT NULL REFERENCES rounds(id),
    division_id  INTEGER NOT NULL REFERENCES divisions(id),
    phase_number INTEGER NOT NULL CHECK (phase_number IN (0, 1, 2, 3)),
    message_id   INTEGER NOT NULL,
    posted_at    TEXT    NOT NULL
);

INSERT INTO forecast_messages_new (id, round_id, division_id, phase_number, message_id, posted_at)
    SELECT id, round_id, division_id, phase_number, message_id, posted_at
    FROM forecast_messages;

DROP TABLE forecast_messages;

ALTER TABLE forecast_messages_new RENAME TO forecast_messages;

CREATE UNIQUE INDEX IF NOT EXISTS uq_forecast_messages_round_div_phase
    ON forecast_messages(round_id, division_id, phase_number);

PRAGMA foreign_keys = ON;
