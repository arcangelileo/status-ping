# StatusPing

Phase: DEPLOYMENT

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
- [x] Design database schema and set up SQLAlchemy models + Alembic migrations (User, Monitor, CheckResult, Incident, StatusPage)
- [x] Implement user registration and JWT authentication (signup, login, logout)
- [x] Build monitor CRUD API (create, read, update, delete monitors with validation)
- [x] Implement uptime check engine (async HTTP checks via httpx, APScheduler job per monitor)
- [x] Build check result storage and retention (store results, prune old data based on plan)
- [x] Implement incident detection and alert system (consecutive failure detection, email alerts on state change)
- [x] Create dashboard UI (monitor list with status indicators, response time charts, uptime percentages)
- [x] Build public status page (per-account page showing all public monitors, uptime bars, current status)
- [x] Add monitor detail view (response time history chart, recent check log, incident history)
- [x] Implement billing/subscription tier logic (enforce monitor limits, check intervals, feature gates)
- [x] Write Dockerfile and docker-compose.yml
- [x] Write README with setup and deployment instructions

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

### Session 3 — AUTH, MONITORS & DASHBOARD
- Generated initial Alembic migration for all models (users, monitors, check_results, incidents, status_pages)
- Built JWT auth system with httponly cookie tokens, bcrypt password hashing
- Implemented auth routes: POST /auth/signup, POST /auth/login (form-based), POST /auth/logout, GET /auth/me
- Full input validation with Pydantic schemas (email, password strength, slug format, URL format)
- Created plan tier system (free/pro/business) with monitor limits and check interval enforcement
- Built full monitor CRUD API: GET/POST /api/monitors, GET/PATCH/DELETE /api/monitors/{id}
- Created professional dashboard UI with monitor list, status indicators, stats bar, add/edit/delete modals
- Dashboard features: auto-refresh every 30s, user menu with profile/logout, responsive design
- Auth guards: dashboard redirects to login for unauthenticated users, API returns 401
- Wrote and passed 33 tests covering auth (13 tests) + monitors (16 tests) + pages (4 tests)

### Session 4 — CHECK ENGINE, STATUS PAGE & MONITOR DETAIL
- Built async uptime check engine (`checker.py`) with httpx: performs HTTP checks, stores CheckResult, updates Monitor status
- Created APScheduler integration (`scheduler.py`): per-monitor scheduled jobs, loads on startup, manages add/remove
- Implemented incident detection: 3 consecutive failures → creates incident (up→down), auto-resolves on recovery (down→up)
- Built email alert system with HTML templates for down/recovery notifications (SMTP when configured)
- Added retention pruning: hourly job deletes old check results based on plan tier (24h/90d/1yr)
- Created professional public status page (`/s/{slug}`) with 90-day uptime bars, per-monitor status, recent incidents
- Added JSON API for status data (`/s/{slug}/api`) for programmatic access
- Built monitor detail view with canvas-based response time chart, check history log, incident history
- Added check results API (`GET /api/monitors/{id}/results`) and uptime stats API (`GET /api/monitors/{id}/uptime`)
- Integrated scheduler with monitor CRUD: creating/updating/deleting monitors auto-manages scheduled jobs
- Dashboard monitor names now link to detail view
- Fixed timezone handling for SQLite naive datetimes in incident resolution
- Added `get_session_factory()` indirection for testable background tasks
- Wrote and passed 54 tests: auth (13) + checker (7) + health (4) + monitors (16) + status page (14)

### Session 5 — DOCKERFILE, DOCKER COMPOSE & README
- Created production-ready multi-stage Dockerfile (Python 3.11-slim, virtualenv-based, non-root user)
- Added docker-entrypoint.sh that runs Alembic migrations before starting the app
- Configured Docker health check against /api/health endpoint
- Finalized docker-compose.yml with named volume for SQLite data persistence, all env vars with defaults
- Wrote .dockerignore to exclude tests, dev files, and database from build context
- Created comprehensive README.md with:
  - Feature overview, tech stack, and quick start (Docker + local dev)
  - Full configuration reference table (all environment variables)
  - Usage guide: account creation, adding monitors, status pages, monitor details
  - Complete API endpoint reference (auth, monitors, status, health)
  - Pricing tier comparison table
  - Project structure overview
  - Production deployment guide with nginx reverse proxy example
  - Test execution instructions
- All 54 tests pass: auth (13) + checker (7) + health (4) + monitors (16) + status page (14)
- All backlog items complete — phase changed to QA

### Session 6 — QA & POLISH
- **Ran full test suite**: all 54 existing tests passed on first run
- **Audited every source file**: all models, routers, schemas, checker, scheduler, templates, tests
- **Bugs found and fixed**:
  1. **Signup form error handling**: Pydantic validation errors (422) returned as array of objects, but JS only handled string `detail` — fixed to parse both array and string formats
  2. **Login form error handling**: Same issue as signup — fixed with proper array/string detection
  3. **Status page animate-ping positioning**: Monitor status dots used `absolute` without `relative` parent container, causing ping animation to render incorrectly — added `relative` to parent span
  4. **Dashboard unused code**: `responseTime` variable computed from non-existent `m.response_time_ms` field (not in MonitorResponse schema) — removed dead code
  5. **Monitor detail page title**: Static "Monitor Detail" title — now dynamically updates to show monitor name via `document.title`
  6. **Missing favicon**: No favicon caused 404 in browsers — added inline SVG favicon matching the StatusPing brand bolt icon
  7. **Mobile action buttons invisible**: Dashboard monitor card edit/pause/delete buttons used `opacity-0 group-hover:opacity-100` which made them invisible on touch devices — changed to `sm:opacity-0 sm:group-hover:opacity-100` so they're always visible on mobile
- **Performance optimization**:
  - Status page uptime bars query reduced from 180+ queries per monitor (2 per day * 90 days) to a single GROUP BY query using `func.date()` and `case()` — massive improvement for pages with multiple monitors
- **UI polish**:
  - Added loading states with disabled buttons on login and signup forms ("Logging in...", "Creating account...")
  - Added `disabled:opacity-50 disabled:cursor-not-allowed` styles to submit buttons
  - Added meta description tag to base template for SEO
  - Added favicon to status_page.html (doesn't extend base.html)
- **New test coverage added (9 new tests, 63 total)**:
  - Auth: logged-in user redirect from /login, /signup, / (3 tests)
  - Auth: signup creates default status page (1 test)
  - Monitors: plan enforcement on interval update (1 test)
  - Checker: connection error handling (1 test)
  - Status page: JSON API 404 for non-existent slug (1 test)
  - Status page: renders properly with zero monitors (1 test)
  - Status page: uptime stats returns zeros when no check results exist (1 test)
- **All 63 tests pass**: auth (17) + checker (8) + health (4) + monitors (17) + status page (17)
- **Phase changed to DEPLOYMENT** — all QA items pass, app is production-ready

## Known Issues
(none)

## Files Structure
```
status-ping/
├── CLAUDE.md                           # Project spec and progress
├── README.md                           # Setup and deployment instructions
├── pyproject.toml                      # Python project config & dependencies
├── Dockerfile                          # Multi-stage Docker build
├── docker-compose.yml                  # Docker Compose configuration
├── docker-entrypoint.sh                # Container entrypoint (runs migrations)
├── .dockerignore                       # Docker build context exclusions
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
│       ├── auth.py                    # JWT auth utilities (hash, token, deps)
│       ├── schemas.py                 # Pydantic request/response schemas
│       ├── plans.py                   # Plan tier limits and features
│       ├── checker.py                # Uptime check engine (HTTP checks, incidents, alerts)
│       ├── scheduler.py              # APScheduler integration (per-monitor jobs)
│       ├── routers/
│       │   ├── __init__.py
│       │   ├── auth.py                # Auth routes (signup, login, logout, me)
│       │   ├── monitors.py           # Monitor CRUD + results/uptime API routes
│       │   ├── pages.py              # Page routes (landing, login, signup, dashboard, detail)
│       │   └── status.py             # Public status page routes (HTML + JSON API)
│       ├── static/                    # Static assets
│       └── templates/
│           ├── base.html              # Base template with nav & footer
│           ├── landing.html           # Landing page with features & pricing
│           ├── login.html             # Login form
│           ├── signup.html            # Signup form
│           ├── dashboard.html         # Dashboard with monitor list & management
│           ├── monitor_detail.html    # Monitor detail with charts & history
│           └── status_page.html       # Public status page with uptime bars
└── tests/
    ├── __init__.py
    ├── conftest.py                    # Test configuration with test DB & fixtures
    ├── test_health.py                 # Health check & page tests (4 tests)
    ├── test_auth.py                   # Auth API tests (17 tests)
    ├── test_monitors.py              # Monitor CRUD API tests (17 tests)
    ├── test_checker.py               # Check engine & incident tests (8 tests)
    └── test_status_page.py           # Status page & detail tests (17 tests)
```
