# eVoteGhana - Prototype Voting System

A Python-based electronic voting system for the Ghanaian electoral context. Covers the full election lifecycle: voter registration (with Ghana Card verification), candidate nomination, polling station assignment, ballot casting with HMAC integrity, multi-level result collation, runoff detection, and audit trail.

## Architecture

```
main.py                          # CLI entry point
├── Registration.py              # Admin setup + voter registration
├── voting.py                    # Ballot casting (MFA, HMAC, rate limited)
├── results_processing.py        # Multi-level collation + EC Ghana forms
├── ballot_creation.py           # Ballot display helpers
├── election.py                  # Phase lifecycle + runoff logic
├── database.py                  # Connection manager
├── config.py                    # .env loader
├── schema.py                    # DB schema (9 normalized tables)
├── audit_log.py                 # Append-only action logger
├── hmac_utils.py                # Vote HMAC integrity + ballot IDs
├── rate_limiter.py              # Auth attempt rate limiting
├── i18n.py                      # Multi-language (EN, Twi, Ewe)
├── age_calc.py                  # Age calculation utility
├── mysql_value_checker.py       # Parameterized DB lookups
├── mysql_delete.py              # Parameterized row deletion
├── prov_Ghcard_details.py       # Ghana Card test data generator
├── tests/                       # Pytest suite (26 tests)
├── Dockerfile                   # Container build
├── docker-compose.yml           # App + MySQL 8
└── .env                         # Credentials + config
```

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

## Quick Start

### Option A: Docker (Recommended)

```bash
docker-compose up --build
# Then attach to the app container:
docker attach evote_app
```

### Option B: Local

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Edit .env with your MySQL credentials, then:
python3 schema.py     # Create database + tables
python3 main.py       # Run the system
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

## EC Ghana Forms

- **Form 1A** — Presidential results (candidate, party, votes, percentage, winner/runoff)
- **Form 1C** — Parliamentary results per constituency

---

*Prototype system for educational and demonstration purposes.*
