import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch

import pytest

import hmac_utils


@pytest.fixture(autouse=True)
def _isolated_keyring(monkeypatch):
    """Keep keyring cache and env isolated for every test in this module."""
    monkeypatch.delenv('HMAC_KEYS', raising=False)
    monkeypatch.delenv('HMAC_KEY_VERSION', raising=False)
    monkeypatch.delenv('HMAC_SECRET_KEY', raising=False)
    hmac_utils._KEYRING_CACHE.clear()
    yield
    hmac_utils._KEYRING_CACHE.clear()


class TestVoteHmacScheme:
    def test_sign_and_verify_roundtrip(self):
        from hmac_utils import compute_vote_hmac, verify_vote_hmac

        sig, version = compute_vote_hmac(3, 7, 'BALLOT-AAAA1111BBBB', 12)
        assert version == 'k1'
        assert verify_vote_hmac(3, 7, 'BALLOT-AAAA1111BBBB', sig, version, 12) is True

    def test_tampered_candidate_detected(self):
        from hmac_utils import compute_vote_hmac, verify_vote_hmac

        sig, _ = compute_vote_hmac(3, 7, 'BALLOT-AAAA1111BBBB', 12)
        assert verify_vote_hmac(3, 8, 'BALLOT-AAAA1111BBBB', sig, 'k1', 12) is False

    def test_tampered_election_detected(self):
        from hmac_utils import compute_vote_hmac, verify_vote_hmac

        sig, _ = compute_vote_hmac(3, 7, 'BALLOT-AAAA1111BBBB', 12)
        assert verify_vote_hmac(4, 7, 'BALLOT-AAAA1111BBBB', sig, 'k1', 12) is False

    def test_tampered_station_detected(self):
        from hmac_utils import compute_vote_hmac, verify_vote_hmac

        sig, _ = compute_vote_hmac(3, 7, 'BALLOT-AAAA1111BBBB', 12)
        assert verify_vote_hmac(3, 7, 'BALLOT-AAAA1111BBBB', sig, 'k1', 13) is False

    def test_tampered_ballot_id_detected(self):
        from hmac_utils import compute_vote_hmac, verify_vote_hmac

        sig, _ = compute_vote_hmac(3, 7, 'BALLOT-AAAA1111BBBB', 12)
        assert verify_vote_hmac(3, 7, 'BALLOT-CCCC3333DDDD', sig, 'k1', 12) is False

    def test_scheme_version_in_message(self):
        """The scheme tag prevents cross scheme signature confusion."""
        import hashlib
        import hmac as hmac_mod

        from hmac_utils import SCHEME_VERSION, _load_keyring, active_key_version, compute_vote_hmac

        raw = f'{SCHEME_VERSION}:3:7:12:BALLOT-X'
        expected = hmac_mod.new(
            _load_keyring()[active_key_version()].encode(), raw.encode(), hashlib.sha256
        ).hexdigest()
        assert compute_vote_hmac(3, 7, 'BALLOT-X', 12)[0] == expected

    def test_signature_covers_no_voter_identity(self):
        """Two voters casting identical ballots produce byte identical signatures."""
        from hmac_utils import compute_vote_hmac

        sig_a, _ = compute_vote_hmac(3, 7, 'BALLOT-SAME000001', 12)
        sig_b, _ = compute_vote_hmac(3, 7, 'BALLOT-SAME000001', 12)
        assert sig_a == sig_b


class TestKeyRotation:
    def test_active_version_honoured(self, monkeypatch):
        import json

        monkeypatch.setenv('HMAC_KEYS', json.dumps({'k1': 'a' * 64, 'k2': 'b' * 64}))
        monkeypatch.setenv('HMAC_KEY_VERSION', 'k2')

        assert hmac_utils.active_key_version() == 'k2'
        sig, version = hmac_utils.compute_vote_hmac(1, 1, 'BALLOT-ROTATE00001', 2)
        assert version == 'k2'
        assert hmac_utils.verify_vote_hmac(1, 1, 'BALLOT-ROTATE00001', sig, 'k2', 2) is True

    def test_old_rows_verify_after_rotation(self, monkeypatch):
        """A row signed under k1 still verifies once k2 is the active version."""
        import json

        monkeypatch.setenv('HMAC_KEYS', json.dumps({'k1': 'a' * 64, 'k2': 'b' * 64}))

        sig_v1, v1 = hmac_utils.compute_vote_hmac(1, 5, 'BALLOT-OLD0000001', 9, key_version='k1')
        monkeypatch.setenv('HMAC_KEY_VERSION', 'k2')
        assert hmac_utils.active_key_version() == 'k2'
        assert hmac_utils.verify_vote_hmac(1, 5, 'BALLOT-OLD0000001', sig_v1, v1, 9) is True

    def test_unknown_recorded_version_fails_closed(self, monkeypatch):
        import json

        monkeypatch.setenv('HMAC_KEYS', json.dumps({'k2': 'b' * 64}))
        hmac_utils._KEYRING_CACHE.clear()
        assert hmac_utils.verify_vote_hmac(1, 1, 'BALLOT-UNKNOWN0001', 'ff' * 32, 'ghost', 2) is False


class TestAuditVotesIntegrity:
    @patch('database.DatabaseManager')
    def test_all_valid_votes(self, mock_db):
        from hmac_utils import audit_votes_integrity, compute_vote_hmac

        rows = []
        for i in range(3):
            bid = f'BALLOT-{i:012X}'
            sig, version = compute_vote_hmac(1, 1, bid, i)
            rows.append((1, 1, i, bid, sig, version))

        conn = MagicMock()
        conn.fetch_all.return_value = rows
        mock_db.return_value.__enter__.return_value = conn

        report = audit_votes_integrity()
        assert report['checked'] == 3
        assert report['valid'] == 3
        assert report['tampered'] == []
        assert report['error'] is None

    @patch('database.DatabaseManager')
    def test_tampered_row_reported_without_identity_leak(self, mock_db):
        from hmac_utils import audit_votes_integrity, compute_vote_hmac

        good_sig, version = compute_vote_hmac(1, 1, 'BALLOT-GOOD000001', 4)
        conn = MagicMock()
        conn.fetch_all.return_value = [
            (1, 1, 4, 'BALLOT-GOOD000001', good_sig, version),
            (2, 1, 4, 'BALLOT-BAD00000001', good_sig, version),
        ]
        mock_db.return_value.__enter__.return_value = conn

        report = audit_votes_integrity()
        assert report['checked'] == 2
        assert report['valid'] == 1
        assert len(report['tampered']) == 1
        assert set(report['tampered'][0].keys()) == {'ballot_paper_id'}

    @patch('database.DatabaseManager')
    def test_database_failure_degrades_gracefully(self, mock_db):
        from hmac_utils import audit_votes_integrity

        conn = MagicMock()
        conn.execute_query.side_effect = RuntimeError('db down')
        mock_db.return_value.__enter__.return_value = conn

        report = audit_votes_integrity()
        assert report['error'] == 'db down'
        assert report['checked'] == 0


class TestBallotPaperId:
    def test_format(self):
        from hmac_utils import generate_ballot_paper_id

        bid = generate_ballot_paper_id()
        assert bid.startswith('BALLOT-')
        assert len(bid) == 19

    def test_uniqueness(self):
        from hmac_utils import generate_ballot_paper_id

        ids = {generate_ballot_paper_id() for _ in range(100)}
        assert len(ids) == 100
