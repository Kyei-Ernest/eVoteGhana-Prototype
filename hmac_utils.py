"""Vote integrity: versioned HMAC signatures, ballot paper IDs, and audits.

Secrecy preserving scheme (``evote-v3``): a signature is computed over exactly
the fields persisted in the ``votes`` table and over nothing that could link a
ballot back to a voter::

    evote-v3:{election_id}:{candidate_id}:{polling_station_id}:{ballot_paper_id}

The signing keys live in a small versioned ring. Every vote row records the
``key_version`` used at signing time, so keys can be rotated without invalidating
historical rows: new ballots adopt the active version while old rows keep
verifying against their own recorded version.
"""

import hashlib
import hmac
import json
import os
import secrets

SCHEME_VERSION = 'evote-v3'
DEFAULT_KEY_VERSION = 'k1'
_KEYRING_CACHE: dict[str, dict[str, str]] = {}


def _load_keyring() -> dict[str, str]:
    """Resolve the keyring once per process.

    Preferred source is the HMAC_KEYS environment variable holding JSON such as
    ``{"k1": "<hex>", "k2": "<hex>"}``. When absent, the single HMAC_SECRET_KEY
    becomes version k1 so simple deployments still work unchanged.
    """
    if 'ring' not in _KEYRING_CACHE:
        raw = os.getenv('HMAC_KEYS', '')
        if raw:
            ring = json.loads(raw)
            if not isinstance(ring, dict) or not ring:
                raise ValueError('HMAC_KEYS must be a non empty JSON object of version to secret.')
        else:
            from config import Config

            base = os.getenv('HMAC_SECRET_KEY') or Config.get_hmac_key()
            if not base or base == 'change-this-to-a-secure-random-key-in-production':
                raise ValueError('A real HMAC key must be configured before votes can be signed.')
            ring = {DEFAULT_KEY_VERSION: base}
        _KEYRING_CACHE['ring'] = {str(k): str(v) for k, v in ring.items()}
    return _KEYRING_CACHE['ring']


def active_key_version() -> str:
    """The version new signatures will use (env HMAC_KEY_VERSION, else k1)."""
    ring = _load_keyring()
    version = os.getenv('HMAC_KEY_VERSION', DEFAULT_KEY_VERSION)
    if version not in ring:
        raise ValueError(f'HMAC_KEY_VERSION {version!r} is not present in the keyring.')
    return version


def compute_vote_hmac(
    election_id: int,
    candidate_id: int,
    ballot_paper_id: str,
    polling_station_id: int | None = None,
    key_version: str | None = None,
) -> tuple[str, str]:
    """Sign the persisted ballot attributes; returns ``(signature, key_version)``."""
    version = key_version or active_key_version()
    key = _load_keyring()[version]
    msg = f'{SCHEME_VERSION}:{election_id}:{candidate_id}:{polling_station_id or ""}:{ballot_paper_id}'
    sig = hmac.new(key.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).hexdigest()
    return sig, version


def verify_vote_hmac(
    election_id: int,
    candidate_id: int,
    ballot_paper_id: str,
    received_hmac: str,
    key_version: str = DEFAULT_KEY_VERSION,
    polling_station_id: int | None = None,
) -> bool:
    """Recompute the signature under the row's recorded key version."""
    try:
        key = _load_keyring()[key_version]
    except KeyError:
        return False  # unknown historical version: cannot verify, treat as failure
    msg = f'{SCHEME_VERSION}:{election_id}:{candidate_id}:{polling_station_id or ""}:{ballot_paper_id}'
    expected = hmac.new(key.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_hmac)


def audit_votes_integrity(limit: int = 100000) -> dict:
    """Scan every stored ballot and report rows whose signature no longer matches.

    Returns ``{'checked': int, 'valid': int, 'tampered': [paper ids], 'error': str|None}``.
    Because ballots carry no voter identity, tampering reports are anonymous by
    design: they identify suspect paper IDs, never voters.
    """
    from database import DatabaseManager

    checked = 0
    valid = 0
    tampered: list[dict] = []
    try:
        with DatabaseManager() as db:
            db.execute_query(
                'SELECT candidate_id, election_id, polling_station_id, ballot_paper_id, hmac_hash, '
                'key_version FROM votes ORDER BY id DESC LIMIT %s',
                (limit,),
            )
            for candidate_id, election_id, station_id, paper_id, sig, version in db.fetch_all():
                checked += 1
                if paper_id and verify_vote_hmac(election_id, candidate_id, paper_id, sig, version or 'k1', station_id):
                    valid += 1
                else:
                    tampered.append({'ballot_paper_id': paper_id})
    except Exception as exc:  # noqa: BLE001 - integrity report degrades gracefully
        return {'checked': checked, 'valid': valid, 'tampered': tampered, 'error': str(exc)}
    return {'checked': checked, 'valid': valid, 'tampered': tampered, 'error': None}


def generate_ballot_paper_id() -> str:
    """Return a random public ballot identifier such as ``BALLOT-9F2C41A0B3D7``."""
    return 'BALLOT-' + secrets.token_hex(6).upper()
