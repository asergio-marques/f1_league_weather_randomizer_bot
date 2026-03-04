-- Migration 003: Remove race_day and race_time from divisions.
-- These fields are redundant: each round already carries its own scheduled_at
-- datetime, which the scheduler uses directly. The division-level day/time
-- inputs have been removed from the /division-add command.

ALTER TABLE divisions DROP COLUMN race_day;
ALTER TABLE divisions DROP COLUMN race_time;
