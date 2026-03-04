# F1 League Weather Randomizer Bot

A Discord bot for F1 league racing servers that delivers an automated, three-phase weather generation pipeline for every race round.
Made using GitHub Copilot Spec Kit and Claude as an experiment.

---

## Prerequisites

- Python 3.8 or higher (3.12+ recommended)
- A Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))

---

## Setup

### 1. Clone & install dependencies

```bash
git clone <repository-url>
cd f1_league_weather_randomizer_bot
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```
BOT_TOKEN=your_discord_bot_token_here
DB_PATH=bot.db
```

### 3. Run the bot

```bash
python src/bot.py
```

On first run the bot will create `bot.db` and apply all schema migrations automatically.

---

## First-time Server Setup

After inviting the bot, a **server administrator** (Manage Server permission) must run:

```
/bot-init interaction_role:@YourRole interaction_channel:#commands log_channel:#bot-logs
```

This registers:
- **Interaction role** -- who can use bot commands
- **Interaction channel** -- the only channel where commands are accepted
- **Log channel** -- where computation audit logs are posted

---

## Slash Commands

### `/bot-init` — One-time server setup
*Access: Server administrator (Manage Server permission)*

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `interaction_role` | Role | ✅ | The Discord role permitted to use bot commands |
| `interaction_channel` | Channel | ✅ | The only channel where bot commands are accepted |
| `log_channel` | Channel | ✅ | Channel where computation audit logs are posted |
| `force` | Boolean | — | Set `True` to overwrite an existing configuration (default: `False`) |

---

### `/bot-reset` — Reset server data
*Access: Server administrator (Manage Server permission) · Can be run from any channel*

Removes all season data for this server. Use `full:True` to also wipe the bot configuration (equivalent to a factory reset).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `confirm` | String | ✅ | Must be exactly `CONFIRM` (case-sensitive) to authorise deletion |
| `full` | Boolean | — | Also deletes bot configuration — you must re-run `/bot-init` afterwards (default: `False`) |

**Partial reset** (`full:False`, the default): deletes all seasons, divisions, rounds, sessions, phase results, and audit entries.  Bot configuration (channel, role) is preserved; the bot remains usable immediately.

**Full reset** (`full:True`): additionally deletes the bot configuration row.  Run `/bot-init` to re-configure the bot for this server.

---

### Season Setup Workflow

Season configuration is a multi-step flow: first run `/season-setup`, then add each division with `/division-add`, then add rounds with `/round-add`, then review and approve.

#### `/season-setup` — Start session wizard
*Access: Trusted admin*

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | String | ✅ | Season start date in `YYYY-MM-DD` format |
| `num_divisions` | Integer | ✅ | Number of divisions to configure (1–10) |

#### `/division-add` — Add a division
*Access: Trusted admin · Requires active `/season-setup` session*

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | String | ✅ | Division name (used to reference it in subsequent commands) |
| `role` | Role | ✅ | Discord role mentioned in weather forecast messages for this division |
| `forecast_channel` | Channel | ✅ | Channel where weather forecast messages are posted |

#### `/round-add` — Add a round to a division
*Access: Trusted admin · Requires active `/season-setup` session*

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `division_name` | String | ✅ | Exact name of the division this round belongs to |
| `round_number` | Integer | ✅ | Round number within the division |
| `format` | String | ✅ | Race format: `NORMAL`, `SPRINT`, `MYSTERY`, or `ENDURANCE` |
| `scheduled_at` | String | ✅ | Race date and time in ISO format: `YYYY-MM-DDTHH:MM:SS` (UTC) |
| `track` | String | — | Track ID or name — use the autocomplete dropdown (e.g. `27` or `United Kingdom`). Omit for Mystery rounds. |

#### `/season-review` — Review pending configuration
*Access: Trusted admin*

No parameters. Displays the pending season configuration with **Approve** and **Go Back to Edit** buttons.

#### `/season-approve` — Commit the configuration
*Access: Trusted admin*

No parameters. Saves all pending divisions and rounds to the database and arms the weather scheduler. Equivalent to pressing Approve in `/season-review`.

---

### Active Season Commands

#### `/season-status` — Active season summary
*Access: Interaction role*

No parameters. Shows active season overview: divisions, next scheduled round per division, and its track and datetime.

#### `/round-amend` — Amend a round in the active season
*Access: Trusted admin*

At least one optional field must be provided.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `division_name` | String | ✅ | Name of the division containing the round |
| `round_number` | Integer | ✅ | The round number to amend |
| `track` | String | — | New track — use the autocomplete dropdown (e.g. `05` or `Bahrain`). Amending invalidates prior weather phases. |
| `scheduled_at` | String | — | New race datetime in ISO format `YYYY-MM-DDTHH:MM:SS` (UTC). Amending re-triggers the scheduler. |
| `format` | String | — | New format: `NORMAL`, `SPRINT`, `MYSTERY`, or `ENDURANCE`. Amending invalidates prior weather phases. |

---

### Test Mode Commands

Test mode allows triggering weather phases on demand without waiting for the real scheduled times. Useful for verifying the bot setup before a live season.

#### `/test-mode toggle` — Enable or disable test mode
*Access: Interaction role*

No parameters. Flips test mode on/off; state persists across bot restarts.

#### `/test-mode advance` — Execute the next pending phase
*Access: Interaction role · Requires test mode active*

No parameters. Immediately runs the next pending weather phase in the queue (ordered by round date, then division). Bypasses all scheduled time checks — rounds can be advanced at any time regardless of their configured date.

#### `/test-mode review` — View phase completion status
*Access: Interaction role · Requires test mode active*

No parameters. Displays a summary of all rounds for the active season, showing which phases (✅/⏳) have been completed per round and division.

---

### Track ID Reference

Use these IDs in `/round-add` and `/round-amend` — autocomplete will show the full list as you type.

| ID | Track | ID | Track | ID | Track |
|----|-------|----|-------|----|-------|
| 01 | Abu Dhabi | 10 | China | 19 | Monza |
| 02 | Australia | 11 | Hungary | 20 | Netherlands |
| 03 | Austria | 12 | Imola | 21 | Portugal |
| 04 | Azerbaijan | 13 | Japan | 22 | Qatar |
| 05 | Bahrain | 14 | Las Vegas | 23 | Saudi Arabia |
| 06 | Barcelona | 15 | Madrid | 24 | Singapore |
| 07 | Belgium | 16 | Mexico | 25 | Texas |
| 08 | Brazil | 17 | Miami | 26 | Turkey |
| 09 | Canada | 18 | Monaco | 27 | United Kingdom |

---

## Weather Pipeline

Three phases fire automatically per round (non-Mystery formats only):

| Phase | Horizon | Output |
|-------|---------|--------|
| Phase 1 | T-5 days | Rain probability coefficient (Rpc) |
| Phase 2 | T-2 days | Rain/mixed/sunny slot per session |
| Phase 3 | T-2 hours | Slot-by-slot weather labels per session |

All forecast messages go to each division forecast channel.
Computation logs go to the server log channel.

---

## Running Tests

```bash
pytest
```

---

## Architecture

```
src/
  bot.py               Entry point
  models/              Dataclasses and enums
  db/                  Database connection + migrations
  services/            Business logic (season, phases, scheduler, amendments)
  cogs/                Discord slash commands
  utils/               Math formulas, message builders, channel guard, output router
tests/
  unit/                Pure-function tests (math_utils)
  integration/         Database migration and query tests
```
