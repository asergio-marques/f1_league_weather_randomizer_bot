# Quickstart: Driver Profiles, Teams & Season Enhancements

**Phase 1 Output** | Feature: `012-driver-profiles-teams` | Date: 2026-03-06

This guide describes how to set up, run, and verify this feature in a development
or test environment once it is implemented.

---

## Prerequisites

- Bot already configured with `/bot-init` on the target Discord test server.
- A Tier-2 admin role member available for testing admin commands.
- Test mode can be toggled on for driver-state testing.
- Standard dev environment: Python 3.12+, dependencies installed (`pip install -r requirements.txt`).

---

## Running the bot with the new migration

When the bot starts, `run_migrations()` in `src/db/database.py` will automatically apply
`008_driver_profiles_teams.sql`. No manual steps are needed.

To verify the migration ran:

```bash
python - <<'EOF'
import asyncio, aiosqlite
async def check():
    async with aiosqlite.connect("bot.db") as db:
        cur = await db.execute("SELECT version FROM schema_migrations ORDER BY version")
        rows = await cur.fetchall()
        for r in rows:
            print(r[0])
asyncio.run(check())
EOF
```

Expected: `008_driver_profiles_teams.sql` appears in the output.

---

## Default Teams Seed Verification

After the first `/bot-init` (or on bot startup against an existing configured server),
check that default teams are seeded:

```bash
python - <<'EOF'
import asyncio, aiosqlite
async def check():
    async with aiosqlite.connect("bot.db") as db:
        cur = await db.execute("SELECT name, max_seats, is_reserve FROM default_teams LIMIT 20")
        for r in await cur.fetchall():
            print(r)
asyncio.run(check())
EOF
```

Expected: 10 constructor rows (max_seats=2, is_reserve=0) + 1 Reserve row (max_seats=-1, is_reserve=1).

---

## Season Number Verification

1. Run `/season setup` → confirm message shows "Season 1".
2. Run `/season cancel` → counter increments.
3. Run `/season setup` → confirm message shows "Season 2".

---

## Division Tier Gate Verification

1. Run `/season setup`.
2. Add two divisions with tiers 1 and 3 (`/division add ... tier:1`, `/division add ... tier:3`).
3. Run `/season approve` → expect error: "Missing tier(s): 2".
4. Delete the tier-3 division, add one at tier 2.
5. Run `/season approve` → proceeds normally.

---

## Team Auto-Creation on Division Add

1. During `/season setup`, run `/division add` with a valid tier.
2. Run `/season review` → the new division section should list all 10 default constructor
   teams (each with 2 "unassigned" seats) plus Reserve.

---

## Default Team Management Verification

1. Run `/team default add name:Prema seats:2`.
2. Add a new division → "Prema" appears in the division team list.
3. Run `/team default remove name:Prema` → confirm and verify it no longer seeds new divisions.

---

## Season Team Management Verification

1. During season SETUP, run `/team season add name:Prema seats:2`.
2. Run `/season review` → all existing divisions show "Prema" team.
3. Run `/season season remove name:Prema`.
4. Run `/season review` → "Prema" gone from all divisions.
5. Approve the season (ACTIVE).
6. Attempt `/team season add name:Test` → expect lifecycle error.

---

## Driver Profile State Machine Verification (via test mode)

1. `/test-mode toggle` → enable.
2. Trigger *Not Signed Up → Unassigned* via test-mode advance for a user.
3. Verify the profile row was created with `current_state = UNASSIGNED`.
4. Trigger *Unassigned → Assigned*.
5. Attempt a disallowed transition (e.g., *Assigned → Pending Signup Completion*) —
   expect rejection message.
6. Trigger *Assigned → League Banned*.
7. Attempt *League Banned → Season Banned* — expect rejection.
8. Trigger *League Banned → Not Signed Up*.
9. Profile row: if `former_driver = false`, row should be deleted. Verify in DB.
10. `/test-mode set-former-driver user:@SomeUser value:True` → confirm flag set.

---

## Driver User ID Reassignment Verification

1. Ensure `@UserA` has a driver profile (any state).
2. Ensure `@UserB` has no profile.
3. Run `/driver reassign old_user:@UserA new_user:@UserB`.
4. Confirm: profile is accessible via User B's ID; User A's ID has no profile.
5. Check audit log for `DRIVER_USER_ID_REASSIGN` entry.
6. Attempt `/driver reassign old_user:@UserA new_user:@UserB` again → expect error
   (no profile for old user).
7. Attempt `/driver reassign old_user:@UserB new_user:@UserA` where UserA now has a
   profile → expect error (target already has profile).

---

## Running the Unit Tests

```bash
pytest tests/unit/test_driver_service.py       -v
pytest tests/unit/test_team_service.py         -v
pytest tests/unit/test_season_tier_validation.py -v
```

## Running the Integration Tests

```bash
pytest tests/integration/test_driver_profiles_teams.py -v
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| `FOREIGN KEY constraint failed` on season approve | Migration not applied; restart bot. |
| `/team season add` errors "No season in setup" | Season was approved or cancelled already. |
| Division tier error even with correct tiers | Duplicate tier from a previous test; delete the duplicate division first. |
| `former_driver` flag not deleteable | Former driver immutability is working correctly — this is expected. |
