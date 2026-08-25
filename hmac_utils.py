"""Vote integrity: HMAC signatures and ballot paper IDs.

Every cast ballot carries an HMAC-SHA256 signature (scheme ``evote-v2``) computed
over exactly the fields that are persisted in the ``votes`` table:

    voter_id | candidate_id | election_id | ballot_paper_id

Signing stored fields means any later tampering with the database can be detected
by recomputing the signature from the row itself (see :func:`audit_votes_integrity`).
The earlier scheme signed a timestamp that was never persisted, which made stored
signatures impossible to verify; rows signed under that scheme will report as
tampered by :func:`audit_votes_integrity` and must be re-signed or discarded.
"""

import hashlib
import hmac
import secrets

from config import Config

SCHEME_VERSION = 'evote-v2'
_HMAC_KEY_CACHE: dict[str, str] = {}


def _get_hmac_key() -> str:
    """Resolve the signing key once per process (env var wins over .env file)."""
    if 'key' not in _HMAC_KEY_CACHE:
        import os

        key = os.getenv('HMAC_SECRET_KEY') or Config.get_hmac_key()
        if not key:
            raise ValueError('HMAC_SECRET_KEY must be configured before votes can be signed.')
        _HMAC_KEY_CACHE['key'] = key
    return _HMAC_KEY_CACHE['key']


def compute_vote_hmac(voter_id: int | str, candidate_id: int, election_id: int, ballot_paper_id: str) -> str:
    """Sign the four persisted vote attributes with HMAC-SHA256."""
    msg = f'{SCHEME_VERSION}:{voter_id}:{candidate_id}:{election_id}:{ballot_paper_id}'
    return hmac.new(
        _get_hmac_key().encode('utf-8'),
        msg.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def verify_vote_hmac(
    voter_id: int | str, candidate_id: int, election_id: int, ballot_paper_id: str, received_hmac: str
) -> bool:
    """Recompute the signature for a stored vote and compare in constant time."""
    expected = compute_vote_hmac(voter_id, candidate_id, election_id, ballot_paper_id)
    return hmac.compare_digest(expected, received_hmac)


def audit_votes_integrity(limit: int = 100000) -> dict:
    """Scan recorded votes and report rows whose signature no longer matches.

    Returns a dict::

        {'checked': int, 'valid': int, 'tampered': [{'ballot_paper_id', ...}], 'error': str|None}

    A mismatch proves the row's voter/candidate/election/ballot fields were edited
    after signing (or the signature itself was rewritten). It cannot prove who made
    the change, only that the record is no longer trustworthy as evidence.
    """
    from database import DatabaseManager

    checked = 0
    valid = 0
    tampered: list[dict] = []
    try:
        with DatabaseManager() as db:
            db.execute_query(
                'SELECT voter_id, candidate_id, election_id, ballot_paper_id, hmac_hash '
                'FROM votes ORDER BY id DESC LIMIT %s',
                (limit,),
            )
            for voter_id, candidate_id, election_id, ballot_paper_id, hmac_hash in db.fetch_all():
                checked += 1
                if ballot_paper_id and verify_vote_hmac(
                    voter_id, candidate_id, election_id, ballot_paper_id, hmac_hash
                ):
                    valid += 1
                else:
                    tampered.append({'ballot_paper_id': ballot_paper_id, 'voter_id': voter_id})
    except Exception as exc:  # noqa: BLE001 - integrity report must degrade gracefully
        return {'checked': checked, 'valid': valid, 'tampered': tampered, 'error': str(exc)}
    return {'checked': checked, 'valid': valid, 'tampered': tampered, 'error': None}


def generate_ballot_paper_id() -> str:
    """Return a random public ballot identifier such as ``BALLOT-9F2C41A0B3D7``."""
    return 'BALLOT-' + secrets.token_hex(6).upper()
