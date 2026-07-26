import hmac
import hashlib
import os
import secrets

from config import Config

HMAC_KEY = None


def _get_hmac_key() -> str:
    global HMAC_KEY
    if HMAC_KEY is None:
        HMAC_KEY = os.getenv('HMAC_SECRET_KEY') or Config.get_hmac_key()
    return HMAC_KEY


def compute_vote_hmac(voter_id: int | str, candidate_id: int, election_id: int, timestamp: str) -> str:
    msg = f"{voter_id}:{candidate_id}:{election_id}:{timestamp}"
    return hmac.new(
        _get_hmac_key().encode('utf-8'),
        msg.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def verify_vote_hmac(voter_id: int | str, candidate_id: int, election_id: int, timestamp: str, received_hmac: str) -> bool:
    expected = compute_vote_hmac(voter_id, candidate_id, election_id, timestamp)
    return hmac.compare_digest(expected, received_hmac)


def generate_ballot_paper_id() -> str:
    return "BALLOT-" + secrets.token_hex(6).upper()
