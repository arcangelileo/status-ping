# StatusPing

Phase: DEVELOPMENT

## Project Spec
- **Repo**: https://github.com/arcangelileo/status-ping
- **Idea**: StatusPing is an uptime monitoring and public status page platform for businesses and developers. Users add monitors (HTTP/HTTPS endpoints) that are checked at configurable intervals (1-5 minutes). When a site goes down, StatusPing sends instant alerts via email and webhook. Each account gets a branded public status page (e.g., status.yourcompany.com or statusping.app/s/yourcompany) showing real-time and historical uptime for all monitors. It replaces expensive tools like Pingdom, UptimeRobot Pro, and Statuspage.io with a simpler, more affordable alternative.
- **Target users**: SaaS companies, agencies, freelance developers, and small businesses who run websites/APIs and need to know immediately when things break. Also teams who need to communicate service status to their customers via a public status page.
- **Revenue model**: Freemium with tiered subscriptions.
  - **Free tier**: Up to 5 monitors, 5-minute check interval, email alerts only, StatusPing-branded status page, 24-hour history.
  - **Pro ($14/mo)**: Up to 50 monitors, 1-minute check interval, email + webhook alerts, custom status page branding, 90-day history, SSL certificate expiry monitoring.
  - **Business ($39/mo)**: Unlimited monitors, 30-second check interval, all alert channels, custom domain for status page, 1-year history, team members, API access, maintenance windows.
- **Tech stack**: Python 3.11+, FastAPI, SQLite (MVP), APScheduler for check scheduling, httpx for async HTTP checks, Jinja2 + Tailwind CSS for UI, Docker.
- **MVP scope**: The first version covers: create an account, add HTTP/HTTPS monitors with configurable check intervals, run automated uptime checks in the background, record response times and status history, send email alerts on status changes (up→down, down→up), display a public status page per account showing current status and uptime percentages, and provide a dashboard with response time charts and uptime stats. No custom domains, no webhook alerts, no SSL monitoring in MVP — those come in later tiers.

## Architecture Decisions
- **FastAPI** with async: critical for non-blocking HTTP checks — we'll be hitting many endpoints concurrently.
- **SQLite** for MVP: single-file DB. Schema designed to be PostgreSQL-compatible. Will need to manage check result table size (rolling retention).
- **APScheduler** with AsyncIOScheduler: schedules per-monitor check jobs. Each monitor gets its own job with its own interval. Jobs are recreated on app startup from DB state.
- **httpx** for HTTP checks: async HTTP client, supports timeouts, redirects, SSL verification. Better than aiohttp for this use case.
- **Check results table**: stores every check result (status code, response time, error message). Pruned based on plan retention (24h/90d/1yr). Indexed on monitor_id + checked_at.
- **Status computation**: uptime percentage calculated from check results over time window. Current status = latest check result. Incident = consecutive failures (3+ checks).
- **Public status pages**: rendered server-side via Jinja2. URL pattern: `/s/{account_slug}`. No auth required. Shows all monitors marked as "public".
- **Alert deduplication**: only alert on state transitions (up→down, down→up), not on every failed check. Require 3 consecutive failures before marking "down" to avoid flapping.
- **JWT auth** with httponly cookies: same pattern as InvoicePulse, proven to work well.
- **Alembic** for migrations from the start.
- **Response time tracking**: store response_time_ms as integer. Display as sparkline/chart on dashboard.
- **Timezone handling**: all timestamps in UTC. Display converted client-side.

## Task Backlog
- [x] Create project structure (pyproject.toml, src layout, .gitignore, alembic init)
- [x] Set up FastAPI app skeleton with health check, CORS, static files, Jinja2 templates
- [ ] Design database schema and set up SQLAlchemy models + Alembic migrations (User, Monitor, CheckResult, Incident, StatusPage)
- [ ] Implement user registration and JWT authentication (signup, login, logout)
- [ ] Build monitor CRUD API (create, read, update, delete monitors with validation)
- [ ] Implement uptime check engine (async HTTP checks via httpx, APScheduler job per monitor)
- [ ] Build check result storage and retention (store results, prune old data based on plan)
- [ ] Implement incident detection and alert system (consecutive failure detection, email alerts on state change)
- [ ] Create dashboard UI (monitor list with status indicators, response time charts, uptime percentages)
- [ ] Build public status page (per-account page showing all public monitors, uptime bars, current status)
- [ ] Add monitor detail view (response time history chart, recent check log, incident history)
- [ ] Implement billing/subscription tier logic (enforce monitor limits, check intervals, feature gates)
- [ ] Write Dockerfile and docker-compose.yml
- [ ] Write README with setup and deployment instructions

## Progress Log
### Session 1 — IDEATION
- Chose idea: StatusPing — uptime monitoring & public status page SaaS
- Target: SaaS companies, developers, agencies needing uptime monitoring and customer-facing status pages
- Revenue: freemium ($0 / $14/mo / $39/mo tiers)
- Created spec, architecture decisions, and task backlog

### Session 2 — SCAFFOLDING
- Created project structure: pyproject.toml, src/app layout, .gitignore, .env.example
- Set up FastAPI app with async lifespan, CORS middleware, static files, Jinja2 templates
- Created SQLAlchemy async models: User, Monitor, CheckResult, Incident, StatusPage
- Set up Alembic migration framework configured for async SQLite
- Built professional landing page with hero, features, and pricing sections (Tailwind CSS)
- Created login and signup page templates with client-side form handling
- Added health check endpoint at /api/health
- Configured pydantic-settings for environment-based config
- Wrote and passed 4 tests (health check, landing, login, signup pages)
- Created GitHub repo: https://github.com/arcangelileo/status-ping

## Known Issues
(none yet)

## Files Structure
```
status-ping/
├── CLAUDE.md                           # Project spec and progress
├── pyproject.toml                      # Python project config & dependencies
├── .gitignore                          # Python/IDE/DB gitignore
├── .env.example                        # Environment variable template
├── alembic.ini                         # Alembic configuration
├── alembic/
│   ├── env.py                          # Async Alembic environment
│   ├── script.py.mako                  # Migration template
│   └── versions/                       # Migration files
├── src/
│   └── app/
│       ├── __init__.py
│       ├── main.py                     # FastAPI app entry point
│       ├── config.py                   # Settings via pydantic-settings
│       ├── database.py                 # Async SQLAlchemy engine & session
│       ├── models/
│       │   ├── __init__.py             # Model exports
│       │   ├── user.py                 # User model
│       │   ├── monitor.py             # Monitor model
│       │   ├── check_result.py        # CheckResult model
│       │   ├── incident.py            # Incident model
│       │   └── status_page.py         # StatusPage model
│       ├── routers/
│       │   ├── __init__.py
│       │   ├── auth.py                # Auth routes (stub)
│       │   ├── monitors.py           # Monitor CRUD routes (stub)
│       │   ├── pages.py              # Page routes (landing, login, signup)
│       │   └── status.py             # Public status page routes (stub)
│       ├── static/                    # Static assets
│       └── templates/
│           ├── base.html              # Base template with nav & footer
│           ├── landing.html           # Landing page with features & pricing
│           ├── login.html             # Login form
│           └── signup.html            # Signup form
└── tests/
    ├── __init__.py
    ├── conftest.py                    # Test configuration
    └── test_health.py                 # Health check & page tests
```
