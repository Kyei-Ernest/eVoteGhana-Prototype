import hmac
import hashlib
import os
import string
import random
from config import Config

HMAC_KEY = os.getenv('HMAC_SECRET_KEY', 'default-vote-integrity-key-change-in-production')


def compute_vote_hmac(voter_id, candidate_id, election_id, timestamp):
    msg = f"{voter_id}:{candidate_id}:{election_id}:{timestamp}"
    return hmac.new(
        HMAC_KEY.encode('utf-8'),
        msg.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def verify_vote_hmac(voter_id, candidate_id, election_id, timestamp, received_hmac):
    expected = compute_vote_hmac(voter_id, candidate_id, election_id, timestamp)
    return hmac.compare_digest(expected, received_hmac)


def generate_ballot_paper_id():
    return "BALLOT-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
