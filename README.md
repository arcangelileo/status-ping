# StatusPing

Uptime monitoring and public status page platform for businesses and developers. Monitor your websites and APIs, get instant alerts when things go down, and share a professional status page with your customers.

StatusPing is a simpler, more affordable alternative to Pingdom, UptimeRobot Pro, and Statuspage.io.

## Features

- **HTTP/HTTPS Monitoring** — Add endpoints and check them at configurable intervals (30s to 5min)
- **Instant Alerts** — Email notifications on status changes (up → down, down → up) with smart deduplication
- **Public Status Pages** — Branded, shareable status pages showing real-time and historical uptime
- **Response Time Charts** — Track performance trends with interactive response time graphs
- **Incident Detection** — Automatic incident creation after consecutive failures, auto-resolution on recovery
- **Dashboard** — Overview of all monitors with status indicators, uptime percentages, and quick actions
- **Tiered Plans** — Free, Pro ($14/mo), and Business ($39/mo) with increasing limits and features
- **REST API** — Programmatic access to monitors, check results, and status data

## Tech Stack

- **Backend**: Python 3.11+, FastAPI (async)
- **Database**: SQLite via SQLAlchemy (async) + Alembic migrations
- **Scheduler**: APScheduler (AsyncIOScheduler) for per-monitor check jobs
- **HTTP Client**: httpx (async) for endpoint checks
- **Frontend**: Jinja2 templates + Tailwind CSS
- **Auth**: JWT tokens with httponly cookies, bcrypt password hashing
- **Containerization**: Docker + Docker Compose

## Quick Start

### Prerequisites

- Python 3.11+ or Docker

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/arcangelileo/status-ping.git
cd status-ping

# Create your environment file
cp .env.example .env
# Edit .env and set a strong SECRET_KEY

# Build and start
docker compose up -d

# The app is now running at http://localhost:8000
```

To stop:

```bash
docker compose down
```

### Option 2: Local Development

```bash
# Clone the repository
git clone https://github.com/arcangelileo/status-ping.git
cd status-ping

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -e ".[dev]"

# Create your environment file
cp .env.example .env
# Edit .env and set a strong SECRET_KEY

# Run database migrations
alembic upgrade head

# Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The app will be available at [http://localhost:8000](http://localhost:8000).

## Configuration

All configuration is done via environment variables (or a `.env` file). See `.env.example` for all available options.

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `change-me-...` | JWT signing key. **Must be changed in production.** |
| `DATABASE_URL` | `sqlite+aiosqlite:///./statusping.db` | Database connection string |
| `BASE_URL` | `http://localhost:8000` | Public URL of the application |
| `DEBUG` | `false` | Enable debug logging |
| `SMTP_HOST` | `localhost` | SMTP server for sending alert emails |
| `SMTP_PORT` | `587` | SMTP server port |
| `SMTP_USERNAME` | _(empty)_ | SMTP authentication username |
| `SMTP_PASSWORD` | _(empty)_ | SMTP authentication password |
| `SMTP_FROM_EMAIL` | `alerts@statusping.app` | Sender email for alerts |
| `SMTP_USE_TLS` | `true` | Use TLS for SMTP connection |
| `DEFAULT_CHECK_INTERVAL` | `300` | Default check interval in seconds |
| `DEFAULT_TIMEOUT` | `30` | HTTP request timeout in seconds |
| `CONSECUTIVE_FAILURES_THRESHOLD` | `3` | Consecutive failures before marking a monitor as down |

## Usage

### 1. Create an Account

Visit the app and sign up with your email. Choose a unique slug for your public status page URL.

### 2. Add Monitors

From the dashboard, click **Add Monitor** and enter:
- **Name** — A friendly label (e.g., "Main Website")
- **URL** — The HTTP/HTTPS endpoint to check (e.g., `https://example.com`)
- **Check Interval** — How often to check (depends on your plan tier)
- **Public** — Whether to show this monitor on your public status page

### 3. View Your Status Page

Your public status page is available at `/s/{your-slug}`. Share this URL with your customers so they can check your service status at any time.

### 4. Monitor Details

Click on any monitor name in the dashboard to see:
- Response time history chart
- Recent check results log
- Incident history

## API Endpoints

### Authentication

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/signup` | Create a new account |
| `POST` | `/auth/login` | Log in (form-based, sets httponly cookie) |
| `POST` | `/auth/logout` | Log out (clears cookie) |
| `GET` | `/auth/me` | Get current user info |

### Monitors

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/monitors` | List all monitors for current user |
| `POST` | `/api/monitors` | Create a new monitor |
| `GET` | `/api/monitors/{id}` | Get monitor details |
| `PATCH` | `/api/monitors/{id}` | Update a monitor |
| `DELETE` | `/api/monitors/{id}` | Delete a monitor |
| `GET` | `/api/monitors/{id}/results` | Get check results (with pagination) |
| `GET` | `/api/monitors/{id}/uptime` | Get uptime statistics |

### Public Status

| Method | Path | Description |
|---|---|---|
| `GET` | `/s/{slug}` | Public status page (HTML) |
| `GET` | `/s/{slug}/api` | Public status data (JSON) |

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Application health check |

## Pricing Tiers

| Feature | Free | Pro ($14/mo) | Business ($39/mo) |
|---|---|---|---|
| Monitors | 5 | 50 | Unlimited |
| Check Interval | 5 min | 1 min | 30 sec |
| Email Alerts | Yes | Yes | Yes |
| Webhook Alerts | — | Yes | Yes |
| Status Page Branding | StatusPing | Custom | Custom |
| Custom Domain | — | — | Yes |
| History Retention | 24 hours | 90 days | 1 year |
| SSL Monitoring | — | Yes | Yes |
| Team Members | — | — | Yes |
| API Access | — | — | Yes |

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_auth.py
```

## Project Structure

```
status-ping/
├── Dockerfile                  # Multi-stage Docker build
├── docker-compose.yml          # Docker Compose configuration
├── docker-entrypoint.sh        # Container entrypoint (runs migrations)
├── pyproject.toml              # Python project config & dependencies
├── alembic.ini                 # Alembic migration config
├── alembic/                    # Database migrations
│   ├── env.py
│   └── versions/
├── src/app/
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Settings via pydantic-settings
│   ├── database.py             # Async SQLAlchemy engine & session
│   ├── auth.py                 # JWT auth utilities
│   ├── schemas.py              # Pydantic request/response schemas
│   ├── plans.py                # Plan tier limits and features
│   ├── checker.py              # Uptime check engine
│   ├── scheduler.py            # APScheduler integration
│   ├── models/                 # SQLAlchemy models
│   │   ├── user.py
│   │   ├── monitor.py
│   │   ├── check_result.py
│   │   ├── incident.py
│   │   └── status_page.py
│   ├── routers/                # API route handlers
│   │   ├── auth.py
│   │   ├── monitors.py
│   │   ├── pages.py
│   │   └── status.py
│   ├── templates/              # Jinja2 HTML templates
│   └── static/                 # Static assets
└── tests/                      # Test suite
    ├── conftest.py
    ├── test_health.py
    ├── test_auth.py
    ├── test_monitors.py
    ├── test_checker.py
    └── test_status_page.py
```

## Deployment

### Docker (Production)

1. Set a strong `SECRET_KEY` in your `.env` file:
   ```bash
   SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
   ```

2. Configure SMTP for email alerts (optional):
   ```env
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your-email@gmail.com
   SMTP_PASSWORD=your-app-password
   SMTP_FROM_EMAIL=alerts@yourdomain.com
   ```

3. Set your public URL:
   ```env
   BASE_URL=https://statusping.yourdomain.com
   ```

4. Build and run:
   ```bash
   docker compose up -d --build
   ```

5. (Optional) Put behind a reverse proxy (nginx, Caddy, Traefik) with TLS.

### Reverse Proxy (nginx example)

```nginx
server {
    listen 443 ssl http2;
    server_name statusping.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/statusping.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/statusping.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## License

Proprietary. All rights reserved.
