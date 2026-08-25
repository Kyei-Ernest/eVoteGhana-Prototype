"""Append only, hash chained audit trail.

Two independent mechanisms protect the audit log:

1. **Structural**: database triggers forbid UPDATE and DELETE outright.
2. **Cryptographic**: every entry embeds the hash of its predecessor, so any
   edit that somehow bypassed the triggers (or a restore from a doctored dump)
   breaks the chain and is detected by :func:`verify_audit_chain`.

The chain input is the canonical string ``prev_hash|action|table_name|record_id|
details|actor|created_at``. The timestamp is an application supplied UTC ISO
string stored verbatim in a varchar column, because TIMESTAMP normalization
(second truncation, timezone mapping, 2038 range) would make byte exact
reproduction impossible at verification time. Lexicographic order of fixed
format UTC strings keeps chronological sorting intact.
"""

import hashlib
from datetime import UTC, datetime

from database import DatabaseManager

GENESIS_HASH = '0' * 64


def _entry_hash(
    prev_hash: str, action: str, table_name: str | None, record_id: str, details: str, actor: str, created_at: str
) -> str:
    canonical = f'{prev_hash}|{action}|{table_name or ""}|{record_id}|{details}|{actor}|{created_at}'
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def log_action(action: str, table_name: str, record_id: str | int, details: str, actor: str = 'system') -> None:
    """Append one chained entry; failures are logged but never break callers."""
    try:
        with DatabaseManager() as db:
            db.execute_query('SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1 FOR UPDATE')
            row = db.fetch_one()
            prev_hash = row[0] if row else GENESIS_HASH
            created_at = datetime.now(UTC).isoformat()
            entry_hash = _entry_hash(prev_hash, action, table_name, str(record_id), str(details), actor, created_at)
            db.execute_query(
                'INSERT INTO audit_log(action, table_name, record_id, details, actor, prev_hash, entry_hash, '
                'created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                (action, table_name, str(record_id), str(details), actor, prev_hash, entry_hash, created_at),
            )
    except Exception as e:  # noqa: BLE001
        print(f'Audit log error: {e}')


def verify_audit_chain(limit: int = 200000) -> dict:
    """Recompute the whole chain; report where it first breaks, if anywhere.

    Returns ``{'checked': int, 'ok': bool, 'broken_after': int|None, 'error': str|None}``
    where ``broken_after`` is the id of the last known good entry.
    """
    checked = 0
    expected_prev = GENESIS_HASH
    try:
        with DatabaseManager() as db:
            db.execute_query(
                'SELECT id, action, table_name, record_id, details, actor, prev_hash, entry_hash, '
                'DATE_FORMAT(created_at, "%Y-%m-%dT%H:%i:%s.%f+00:00") FROM audit_log ORDER BY id LIMIT %s',
                (limit,),
            )
            for row in db.fetch_all():
                entry_id, action, table_name, record_id, details, actor, prev_hash, entry_hash, created_at = row
                if prev_hash != expected_prev:
                    return {
                        'checked': checked,
                        'ok': False,
                        'broken_after': checked and entry_id - 1 or None,
                        'error': f'entry {entry_id} links to unexpected predecessor',
                    }
                computed = _entry_hash(
                    prev_hash, action, table_name, str(record_id), str(details or ''), actor or '', created_at or ''
                )
                if not hmac_compare(entry_hash, computed):
                    return {
                        'checked': checked,
                        'ok': False,
                        'broken_after': entry_id - 1,
                        'error': f'entry {entry_id} content does not match its recorded hash',
                    }
                expected_prev = entry_hash
                checked += 1
        return {'checked': checked, 'ok': True, 'broken_after': None, 'error': None}
    except Exception as exc:  # noqa: BLE001
        return {'checked': checked, 'ok': False, 'broken_after': None, 'error': str(exc)}


def hmac_compare(a: str, b: str) -> bool:
    """Constant time string comparison without importing hmac into templates."""
    import hmac as _hmac

    return _hmac.compare_digest(str(a), str(b))


def get_audit_trail(table_name: str | None = None, record_id: str | None = None, limit: int = 100) -> list[tuple]:
    try:
        with DatabaseManager() as db:
            if table_name and record_id:
                db.execute_query(
                    'SELECT * FROM audit_log WHERE table_name = %s AND record_id = %s '
                    'ORDER BY created_at DESC LIMIT %s',
                    (table_name, str(record_id), limit),
                )
            elif table_name:
                db.execute_query(
                    'SELECT * FROM audit_log WHERE table_name = %s ORDER BY created_at DESC LIMIT %s',
                    (table_name, limit),
                )
            else:
                db.execute_query('SELECT * FROM audit_log ORDER BY created_at DESC LIMIT %s', (limit,))
            return db.fetch_all()
    except Exception as e:  # noqa: BLE001
        print(f'Audit trail error: {e}')
        return []
