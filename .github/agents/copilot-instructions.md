# f1_league_weather_randomizer_bot Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-04

## Active Technologies
- Python 3.13.2 (targets 3.8+) + discord.py 2.7.1 (`app_commands.Choice`, `@command.autocomplete`), aiosqlite ≥ 0.19, APScheduler ≥ 3.10 (003-track-id-autocomplete)
- SQLite via aiosqlite; schema versioned with sequential SQL migration files applied on startup (003-track-id-autocomplete)

- Python 3.13.2 (targets 3.8+) + discord.py 2.7.1, aiosqlite ≥ 0.19, APScheduler ≥ 3.10 (002-test-mode)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.13.2 (targets 3.8+): Follow standard conventions

## Recent Changes
- 003-track-id-autocomplete: Added Python 3.13.2 (targets 3.8+) + discord.py 2.7.1 (`app_commands.Choice`, `@command.autocomplete`), aiosqlite ≥ 0.19, APScheduler ≥ 3.10

- 002-test-mode: Added Python 3.13.2 (targets 3.8+) + discord.py 2.7.1, aiosqlite ≥ 0.19, APScheduler ≥ 3.10

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
