import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch


class TestVoteHmacScheme:
    def test_sign_and_verify_roundtrip(self):
        from hmac_utils import compute_vote_hmac, verify_vote_hmac

        sig = compute_vote_hmac('VOTER1', 7, 3, 'BALLOT-AAAA1111BBBB')
        assert verify_vote_hmac('VOTER1', 7, 3, 'BALLOT-AAAA1111BBBB', sig) is True

    def test_tampered_candidate_detected(self):
        from hmac_utils import compute_vote_hmac, verify_vote_hmac

        sig = compute_vote_hmac('VOTER1', 7, 3, 'BALLOT-AAAA1111BBBB')
        assert verify_vote_hmac('VOTER1', 8, 3, 'BALLOT-AAAA1111BBBB', sig) is False

    def test_tampered_voter_detected(self):
        from hmac_utils import compute_vote_hmac, verify_vote_hmac

        sig = compute_vote_hmac('VOTER1', 7, 3, 'BALLOT-AAAA1111BBBB')
        assert verify_vote_hmac('VOTER2', 7, 3, 'BALLOT-AAAA1111BBBB', sig) is False

    def test_tampered_ballot_id_detected(self):
        from hmac_utils import compute_vote_hmac, verify_vote_hmac

        sig = compute_vote_hmac('VOTER1', 7, 3, 'BALLOT-AAAA1111BBBB')
        assert verify_vote_hmac('VOTER1', 7, 3, 'BALLOT-CCCC3333DDDD', sig) is False

    def test_scheme_version_in_message(self):
        """The scheme tag prevents cross-scheme signature confusion."""
        import hashlib
        import hmac as hmac_mod

        from hmac_utils import SCHEME_VERSION, _get_hmac_key, compute_vote_hmac

        raw = f'{SCHEME_VERSION}:VOTER1:7:3:BALLOT-X'
        expected = hmac_mod.new(_get_hmac_key().encode(), raw.encode(), hashlib.sha256).hexdigest()
        assert compute_vote_hmac('VOTER1', 7, 3, 'BALLOT-X') == expected


class TestAuditVotesIntegrity:
    @patch('database.DatabaseManager')
    def test_all_valid_votes(self, mock_db):
        from hmac_utils import audit_votes_integrity, compute_vote_hmac

        rows = []
        for i in range(3):
            bid = f'BALLOT-{i:012X}'
            sig = compute_vote_hmac(f'V{i}', 1, 1, bid)
            rows.append((f'V{i}', 1, 1, bid, sig))

        conn = MagicMock()
        conn.fetch_all.return_value = rows
        mock_db.return_value.__enter__.return_value = conn

        report = audit_votes_integrity()
        assert report['checked'] == 3
        assert report['valid'] == 3
        assert report['tampered'] == []
        assert report['error'] is None

    @patch('database.DatabaseManager')
    def test_tampered_row_reported(self, mock_db):
        from hmac_utils import audit_votes_integrity, compute_vote_hmac

        good_sig = compute_vote_hmac('V1', 1, 1, 'BALLOT-GOOD000001')
        conn = MagicMock()
        conn.fetch_all.return_value = [
            ('V1', 1, 1, 'BALLOT-GOOD000001', good_sig),
            ('V2', 2, 1, 'BALLOT-BAD00000001', good_sig),  # rewritten vote, old signature kept
        ]
        mock_db.return_value.__enter__.return_value = conn

        report = audit_votes_integrity()
        assert report['checked'] == 2
        assert report['valid'] == 1
        assert len(report['tampered']) == 1
        assert report['tampered'][0]['ballot_paper_id'] == 'BALLOT-BAD00000001'

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
