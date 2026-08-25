# Production Readiness Checklist

An educational artifact: each item states what a real deployment must be able to prove, what this prototype implements, and what remains. Working through it teaches the distance between a well engineered prototype and a certified public election system.

## 1. Software engineering

| # | Requirement | Status in this codebase |
|---|-------------|-------------------------|
| 1 | Automated test suite gating every change | done: 106 tests across integrity, lifecycle, concurrency semantics, web routes |
| 2 | Static analysis and formatting gates in CI | done: ruff check plus format gate |
| 3 | Parameterised SQL everywhere with identifier whitelists | done |
| 4 | Secret ballots at storage level | done: votes carry no voter identity; roll stores only used flags |
| 5 | Tamper evident audit trail | done: append only triggers plus hash chain verifier |
| 6 | Verifiable ballot signatures with key rotation | done: versioned keyring per row |
| 7 | Race safe double voting prevention | done: conditional update slot claims under row locks |
| 8 | Connection pooling and shared rate limiting | done |
| 9 | Admin second factor | done: TOTP enrollment and enforced verification |
| 10 | Non root containers and least privilege database user | done |

## 2. Operations

| # | Requirement | Status |
|---|-------------|--------|
| 1 | Health endpoint exercising dependencies | done |
| 2 | Scheduled backups with retention pruning | done: hourly sidecar, seven days |
| 3 | Restore drills on a schedule | documented in RUNBOOK, not automated |
| 4 | Centralised log aggregation and alerting | not implemented: logs are structured stdout only |
| 5 | Metrics endpoint and dashboards | not implemented |

## 3. Security assurance beyond the code

| # | Requirement | Status |
|---|-------------|--------|
| 1 | Independent penetration test | required before any real use |
| 2 | Third party cryptographic review of the signing and chain design | required before any real use |
| 3 | Documented threat model reviewed by operators | THESIS chapter 8 plus RUNBOOK provide the draft |
| 4 | Physical key ceremony with dual control | described educationally; requires real procedure and witnesses |
| 5 | Incident response plan rehearsed with staff | RUNBOOK quick card is the seed |

## 4. Electoral legitimacy

| # | Requirement | Status |
|-----|-------------|--------|
| 1 | Legal authorisation from the electoral authority | outside software scope entirely |
| 2 | Certification against applicable election system standards | outside software scope |
| 3 | Voter verifiable paper or cryptographic end to end proofs | future work; see THESIS chapter 14 |
| 4 | Accessibility conformance review | partial: server rendered forms, full WCAG audit outstanding |
| 5 | Multilingual completeness including ballot content | partial: Twi and Ewe menus incomplete |

## 5. The honest bottom line

This repository now demonstrates every major engineering discipline that production election software demands: secrecy by architecture, integrity by cryptography plus structure, abuse resistance shared across workers, least privilege everywhere, and operational documentation. What it cannot demonstrate is institutional trust, which is earned through audit, certification, law, and time. For teaching, for organisational pilots inside trusted networks, and as a reference implementation, it is ready.
