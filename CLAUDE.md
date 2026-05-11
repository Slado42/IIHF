# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Behavior

1. **Don't assume. Don't hide confusion. Surface tradeoffs.** If something is ambiguous, ask. If two approaches have meaningful differences, name them before picking one.
2. **Minimum code that solves the problem. Nothing speculative.** No helper abstractions, no "just in case" handling, no cleanup beyond the task at hand.
3. **Touch only what you must. Clean up only your own mess.** Don't refactor surrounding code, rename unrelated things, or improve style in files you're already editing for a different reason.
4. **Define success criteria. Loop until verified.** Before starting, state what "done" looks like. After changes, verify it — run the server, hit the endpoint, check the DB value.

---

## Architecture

This is a fantasy hockey app for the annual IIHF World Championship. Players pick a daily lineup of 8 (6 skaters + 1 captain + 1 goalie); fantasy points are calculated from real match stats scraped from iihf.com.

### Data pipeline

```
IIHF website (iihf.com)
  ↓  Playwright + stealth (bypasses Cloudflare)
url_scraper.py          → match_urls.csv
lineups_scraper.py      → lineups.csv
  ↓
web/backend/scraper_bridge.py   (CLI: players / matches / stats <id>)
  ↓
PostgreSQL / SQLite (via DATABASE_URL env var)
  ↓
FastAPI backend  (web/backend/app/)
  ↓
React frontend   (web/frontend/src/)
```

The backend runs an **hourly background loop** (`_auto_score_loop` in `app/main.py`) that finds matches finished 5+ hours ago, scrapes their stats with Playwright, and recalculates user scores. This is the only automated scoring path — no cron jobs.

### Key constraints

- **Cloudflare**: All IIHF page scraping must use `playwright_stealth`. Plain `requests` gets 403.
- **Match times**: Stored as **UTC** in the DB. Scraped times are Prague/local (CEST = UTC+2 in May); `scraper_bridge.py` converts via `zoneinfo('Europe/Prague')`. The frontend appends `'Z'` to all datetime strings before parsing.
- **Lock logic**: A player's lineup slot locks the moment `match_time <= datetime.now(UTC)`. Lock status is computed per-request in `routers/lineup.py` — not stored.
- **DB connection**: `DATABASE_URL` env var selects Postgres (production) or SQLite fallback. Always set `DATABASE_URL` when running scrapers locally if you want to write to Supabase.

### Backend (`web/backend/`)

- `app/main.py` — FastAPI app, CORS, startup hook, auto-score loop
- `app/models.py` — SQLAlchemy models: `User`, `Player`, `Match`, `PlayerStat`, `DailyLineup`, `UserDayScore`
- `app/routers/` — `auth`, `players`, `matches`, `lineup`, `scores`, `admin`
- `app/scoring.py` — fantasy points formula (position-aware; captain = 2×)
- `scraper_bridge.py` — imports scraped data into the DB; also called by the auto-score loop at runtime

### Frontend (`web/frontend/src/`)

- `App.tsx` — router + layout
- `pages/` — Dashboard (lineup builder), Standings, History
- `api/client.ts` — axios instance with JWT interceptor
- `context/AuthContext.tsx` — auth state
- `components/MatchCountdown.tsx` — polls every 30s; uses `new Date(match_time + 'Z')` for lock countdown

---

## Commands

### Backend

```bash
cd web/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Tests:
```bash
pytest tests/ -v
pytest tests/test_lineup.py -v          # single file
```

Import data into DB (set DATABASE_URL first for Supabase):
```bash
python scraper_bridge.py matches
python scraper_bridge.py players
python scraper_bridge.py stats <match_id>
```

### Frontend

```bash
cd web/frontend
pnpm install
pnpm run dev          # Vite dev server on :5173
pnpm run build
pnpm run test
```

### Scrapers (run from repo root)

```bash
python url_scraper.py         # → match_urls.csv  (run before scraper_bridge matches)
python lineups_scraper.py     # → lineups.csv + uploads to Google Sheets
python check_player_data.py   # reports player count in DB; exits 1 if < 200
```

---

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | Production | `postgresql://...`; defaults to local SQLite |
| `SECRET_KEY` | Production | JWT signing key |
| `CHAMPIONSHIP_URL` | Optional | Defaults to value in `config.py` |
| `VITE_API_URL` | Frontend | Backend base URL; defaults to `http://localhost:8000` |
| `PLAYWRIGHT_BROWSERS_PATH` | Render only | Set to `/opt/render/project/src` in `render.yaml` |

---

## Deployment

Render.com auto-deploys from the `main` branch. Config in `web/backend/render.yaml`. The build step installs Playwright's Chromium (`playwright install chromium --with-deps`).

The admin endpoint `POST /admin/scrape-players` (JWT-protected) triggers a fresh player roster scrape from inside the deployed environment — useful since there's no shell access on Render.
