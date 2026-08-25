# Operations Runbook

A teaching runbook: it documents how this system would be operated day to day and, just as importantly, why each procedure exists. Use it as a model when comparing against real world election operations.

## 1. Deployment sequence

| Step | Action | Why it exists |
|------|--------|---------------|
| 1 | Provision a Linux host with Docker and open ports 80 and 443 | Caddy obtains certificates over HTTP then serves HTTPS |
| 2 | Copy .env.example to .env and set every placeholder with generated secrets | Placeholder values are refused by design at startup |
| 3 | Generate signing keys: python3 -c "import secrets; print(secrets.token_hex(32))" for each version you want in HMAC_KEYS | One key per version enables rotation without invalidating history |
| 4 | docker compose up -d --build then watch docker compose ps until web is healthy | The health check exercises a real database round trip, not just process liveness |
| 5 | Browse https://your-domain/admin/login, sign in, enroll TOTP from Account security before anything else | Admin accounts are the highest value target; enroll the second factor before creating elections |
| 6 | Run one full election lifecycle in staging data, then reset | Rehearsal exposes configuration drift while it is cheap |

```mermaid
flowchart LR
    A[Host ready] --> B[Secrets generated]
    B --> C[Stack started]
    C --> D[Health check green]
    D --> E[Admin 2FA enrolled]
    E --> F[Election configured]
    F --> G[Voting opens]
```

## 2. Key management

| Procedure | Steps |
|-----------|-------|
| Initial key ceremony | Generate two independent keys on an offline machine; publish only into .env; record versions k1 and k2; set HMAC_KEY_VERSION to k1 |
| Routine rotation | Add kN plus its fresh secret to HMAC_KEYS; change HMAC_KEY_VERSION to kN; restart web container; verify old ballots still pass /verify lookups |
| Suspected key compromise | Add replacement version immediately; move active pointer; run the integrity audit from the admin audit page; treat every ballot signed under the compromised version as reviewable evidence |

The rule that makes rotation safe: verification always uses the key version recorded on each row, never the currently active one.

## 3. Backup and restore discipline

1. The backup sidecar dumps and gzips the database hourly and prunes after seven days.
2. An untested backup is a rumour: monthly, restore the latest dump into a scratch database and confirm the audit chain verifier reports OK against it.
3. Before any schema migration against real data, take an on demand backup from the admin page and download it off host.
4. Restores of pre secrecy migration databases will drop the historical voter ballot linkage during bootstrap; this destruction of linkage is intentional privacy remediation and cannot be undone.

## 4. Monitoring and what to alert on

| Signal | Threshold | Interpretation |
|--------|-----------|----------------|
| healthz status degraded | any occurrence | Database unreachable or query failing |
| Audit chain broken | any occurrence | Treat as a security incident, not a bug; snapshot volumes before touching anything |
| Ballot signature failures | greater than zero | Storage tampering or key loss; freeze the affected election phase |
| Failed Ghana Card matches spike | three standard deviations above hourly baseline | Credential stuffing or voter confusion wave |
| Rate limiter fail open warnings | any sustained occurrence | Database pressure is silently disabling abuse controls |

## 5. Incident response quick card

1. Preserve first: copy database volume and logs before remediation.
2. Classify: availability incident versus integrity suspicion.
3. For integrity suspicion: run integrity audits, export the audit chain report, move the election back out of voting phase if open, notify stakeholders with facts only.
4. Never edit audit rows, ever, under any circumstance; the chain exists so that even your own corrections leave evidence.

## 6. Scaling notes

1. uvicorn workers share state only through MySQL; rate limiting already does, sessions do not need shared state because they are signed cookies.
2. DB_POOL_SIZE should approximate workers times expected concurrency divided by query latency budget; eight suits the default two worker deployment.
3. Read heavy result pages can be cached at the proxy once an election reaches results phase because tallies become append only by lifecycle rules.
