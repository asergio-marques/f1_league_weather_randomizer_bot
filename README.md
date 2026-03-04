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

| Command | Access | Description |
|---------|--------|-------------|
| `/bot-init` | Server admin | One-time bot configuration |
| `/season-setup` | Trusted admin | Start interactive season configuration wizard |
| `/division-add` | Trusted admin | Add a division to the pending season |
| `/round-add` | Trusted admin | Add a round to a division in the pending season |
| `/season-review` | Trusted admin | Review pending config with Approve/Cancel buttons |
| `/season-approve` | Trusted admin | Commit configuration and arm the weather scheduler |
| `/season-status` | Interaction role | Read-only summary of active season |
| `/round-amend` | Trusted admin | Amend a round (invalidates prior forecasts) |

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
