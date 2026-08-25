# eVoteGhana - Prototype Voting System

A Python-based electronic voting system for the Ghanaian electoral context. Covers the full election lifecycle: voter registration (with Ghana Card verification), candidate nomination, polling station assignment, ballot casting with HMAC integrity, multi-level result collation, runoff detection, and audit trail.

## Architecture

```
main.py                          # CLI entry point (still supported)
web/app.py                       # FastAPI web application (recommended)
web/security.py                  # Sessions, CSRF, rate limiting, auth deps
web/bootstrap.py                 # Non-interactive first-run DB setup
web/templates/                   # Jinja2 templates
web/static/                      # CSS
├── Registration.py              # Admin setup + voter registration
├── voting.py                    # Ballot casting (MFA, HMAC, rate limited)
├── results_processing.py        # Multi-level collation + EC Ghana forms
├── ballot_creation.py           # Ballot display helpers
├── election.py                  # Phase lifecycle + runoff logic
├── database.py                  # Connection manager
├── config.py                    # .env loader
├── schema.py                    # DB schema (normalized tables)
├── audit_log.py                 # Append-only action logger
├── hmac_utils.py                # Vote HMAC integrity + ballot IDs
├── rate_limiter.py              # Auth attempt rate limiting
├── i18n.py                      # Multi-language (EN, Twi, Ewe)
├── age_calc.py                  # Age calculation utility
├── mysql_value_checker.py       # Parameterized DB lookups
├── mysql_delete.py              # Parameterized row deletion
├── prov_Ghcard_details.py       # Ghana Card test data generator
├── tests/                       # Pytest suite
├── Dockerfile                   # Web app container (uvicorn)
├── docker-compose.yml           # MySQL 8 + web + Caddy TLS + hourly backups
├── Caddyfile                    # Reverse proxy with automatic HTTPS
├── backup/                      # Scheduled backup container (hourly dumps)
└── .env                         # Credentials + config (gitignored)
```

## Web Application

The system ships as a production-oriented web app (FastAPI + server-rendered templates)
in addition to the original CLI. It covers the same election lifecycle and reuses the
same business logic (HMAC vote integrity, phase enforcement, rate limiting, audit log,
results collation):

- **Public** — voter registration, MFA voting (password + Ghana Card), ballot
  verification by ballot paper ID, and results (Form 1A / 1C).
- **Admin** — login, election creation and phase transitions, regions/constituencies/
  polling stations/parties/candidates setup, voter list, audit trail, on-demand backup.
- **Security** — signed HTTP-only session cookies, CSRF tokens on every form, bcrypt
  password hashing, rate-limited logins, security headers, parameterized SQL.
- **Ops** — `/healthz` health check, request logging, first-run bootstrap that creates
  the schema and the initial admin from `ADMIN_USERNAME`/`ADMIN_PASSWORD`, and a
  scheduled hourly `mysqldump` backup container.

### Run with Docker (web)

```bash
cp .env.example .env        # set DB_PASSWORD, SECRET_KEY, HMAC_SECRET_KEY, ADMIN_*
docker compose up -d --build
docker compose ps           # wait until web is healthy
```

Open `https://localhost` (or your `DOMAIN`) and log in with the admin credentials
from `.env`. Point a real domain's DNS at the host and set `DOMAIN` in `.env` to get
a Let's Encrypt certificate automatically. If ports 80/443 are taken, set
`HTTP_PORT` / `HTTPS_PORT` in `.env`.

### Run the web app locally

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # point at your MySQL, set SECRET_KEY and ADMIN_*
uvicorn web.app:app --reload
```

On first boot the app creates the database, tables, seeded regions, and the initial
admin account automatically — no interactive schema setup needed.

## CLI (legacy)

The original terminal interface still works: `python3 main.py`. The CLI uses an
in-memory admin session; the web app has its own session handling.

## Database Schema (Normalized)

| Table | Purpose |
|---|---|
| `regions` | 16 regions of Ghana (seeded) |
| `constituencies` | Constituencies FK to regions |
| `polling_stations` | Stations FK to constituencies |
| `parties` | Political parties |
| `elections` | Election events with phase lifecycle |
| `candidates` | President/MP candidates FK to parties, constituencies, elections |
| `voterinfo` | Voters FK to constituencies, polling stations |
| `votes` | Cast votes with HMAC hash + ballot paper ID |
| `pass_table` | Bcrypt-hashed passwords |
| `audit_log` | Append-only action log |

## Features

### Electoral Integrity
- **HMAC-signed votes** — Each vote has a SHA-256 HMAC over `(voter_id:candidate_id:election_id:timestamp)` to detect tampering
- **Ballot paper IDs** — Unique `BALLOT-XXXX` printed for every vote so voters can verify their vote was counted
- **Append-only audit log** — Every action (registration, voting, phase change) is logged immutably
- **Rate limiting** — 5 auth attempts per 5 minutes, 10 registrations per hour

### Authentication
- **Multi-factor** — Password (bcrypt) + Ghana Card personal ID required to vote
- **Secure input** — `getpass` for all password fields (never echoed to terminal)

### Election Lifecycle
Phases enforced by `election.py` — actions blocked unless in the correct phase:
`nomination → campaigning → voting → results → closed`

### Results Processing
- **Multi-level collation** — Per-constituency → regional summary → national
- **EC Ghana forms** — Form 1A (presidential) and Form 1C (parliamentary) output
- **Runoff detection** — Automatically checks 50%+1 constitutional threshold

### Polling Station Management
Voters are assigned to specific polling stations. Each station has a unique code.

### Recent Upgrades (2026)

| Upgrade | What it means |
|---------|---------------|
| Verifiable ballot signatures | Every vote is HMAC signed over its stored fields; run the integrity audit any time to detect tampering |
| Atomic ballot claims | Double voting is impossible even when two requests arrive simultaneously |
| Enforced audit trail | Database triggers make audit_log physically append only |
| Strict lifecycle | Elections move forward only; closing requires the results phase; denials are logged |
| Runoff workflow | One click creates a runoff election seeded with the top two candidates per Article 63(5) |
| Turnout reporting | Results pages show registered voters, ballots cast, and participation percentage |
| Cryptographic verification | /verify and the CLI now report signature health, not just existence |
| Unique Ghana Cards | A unique index makes duplicate registration impossible at storage level |

## Quick Start

### Option A: Docker (Recommended — web app)

See [Run with Docker (web)](#run-with-docker-web) above. The old CLI container
mode (`docker attach`) is no longer the primary path.

### Option B: Local CLI

```bash
# 1. Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure database credentials
cp .env.example .env
# Edit .env with your MySQL credentials (DB_HOST, DB_USER, DB_PASSWORD)

# 3. Create database and tables (will prompt for admin account on first run)
python3 schema.py

# 4. Start the CLI
python3 main.py
```

## Setup Order

1. **Create election** — `Admin Setup → Manage Elections → Create election`
2. **Add regions** — Already seeded (16 regions of Ghana)
3. **Add constituencies** — Link to regions
4. **Add polling stations** — Link to constituencies
5. **Add parties** — e.g., NPP, NDC
6. **Add presidential candidates** — Link to party + election
7. **Add MP candidates** — Link to party, constituency, election
8. **Register voters** — Assign to constituency + polling station
9. **Transition election to `voting` phase**
10. **Voters cast ballots** — Password + Ghana Card MFA
11. **Transition election to `results` phase**
12. **View results** — Form 1A / Form 1C output

## Multi-Language

Set `LANGUAGE=en|tw|ee` in `.env` to switch between English, Twi, and Ewe.

## Testing

```bash
python3 -m pytest tests/ -v
```

The suite covers the business logic (elections, HMAC, rate limiting, validation,
registration, voting) and web-layer smoke tests with a mocked database.

## EC Ghana Forms

- **Form 1A** — Presidential results (candidate, party, votes, percentage, winner/runoff)
- **Form 1C** — Parliamentary results per constituency

---

*Prototype system for educational and demonstration purposes.*
