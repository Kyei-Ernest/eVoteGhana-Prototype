import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestVerifyPassword:
    def test_verify_password_correct(self):
        import bcrypt

        from voting import verify_password

        hashed = bcrypt.hashpw(b'correct_password', bcrypt.gensalt())
        assert verify_password(hashed, 'correct_password') is True

    def test_verify_password_incorrect(self):
        import bcrypt

        from voting import verify_password

        hashed = bcrypt.hashpw(b'correct_password', bcrypt.gensalt())
        assert verify_password(hashed, 'wrong_password') is False

    def test_verify_password_accepts_str_stored(self):
        import bcrypt

        from voting import verify_password

        hashed = bcrypt.hashpw(b'correct_password', bcrypt.gensalt()).decode('utf-8')
        assert verify_password(hashed, 'correct_password') is True


class TestVoteMp:
    @patch('voting.DatabaseManager')
    @patch('voting.bc.get_mp_election_id', return_value=1)
    @patch('voting.require_phase', return_value=True)
    @patch('voting.bc.display_mp', return_value={'1': 'Candidate A'})
    def test_vote_mp_success(self, mock_display, mock_phase, mock_mp_id, mock_db):
        from voting import vote_mp

        mock_conn = MagicMock()
        mock_conn.cursor.rowcount = 1
        mock_conn.fetch_one.side_effect = [(False, 1, 'GHA-ABCD1234EF'), ('hashed_password',)]
        mock_db.return_value.__enter__.return_value = mock_conn

        with (
            patch('builtins.input', side_effect=['VOTER1', '1']),
            patch('getpass.getpass', side_effect=['GHA-ABCD1234EF', 'password']),
            patch('voting.verify_password', return_value=True),
        ):
            vote_mp()

        assert mock_conn.execute_query.call_count >= 3

    @patch('voting.voter_auth_limiter')
    def test_vote_mp_rate_limited(self, mock_limiter):
        from voting import vote_mp

        mock_limiter.is_allowed.return_value = False

        with patch('builtins.input', return_value='VOTER1'):
            vote_mp()


class TestVotePresident:
    @patch('voting.DatabaseManager')
    @patch('voting.bc.get_presidential_election_id', return_value=1)
    @patch('voting.require_phase', return_value=True)
    @patch('voting.bc.display_presidents', return_value={'1': 'Presidential Candidate'})
    def test_vote_president_success(self, mock_display, mock_phase, mock_pres_id, mock_db):
        from voting import vote_president

        mock_conn = MagicMock()
        mock_conn.cursor.rowcount = 1
        mock_conn.fetch_one.return_value = (None, None)
        mock_db.return_value.__enter__.return_value = mock_conn

        with patch('builtins.input', return_value='1'):
            vote_president('VOTER1')

        queries = [c.args[0] for c in mock_conn.execute_query.call_args_list]
        assert any('president_voted' in q for q in queries)
        assert any('INSERT INTO votes' in q for q in queries)

    @patch('voting.DatabaseManager')
    @patch('voting.bc.get_presidential_election_id', return_value=1)
    @patch('voting.require_phase', return_value=True)
    @patch('voting.bc.display_presidents', return_value={'1': 'Presidential Candidate'})
    def test_vote_president_rejects_double_voting(self, mock_display, mock_phase, mock_pres_id, mock_db):
        from voting import vote_president

        mock_conn = MagicMock()
        mock_conn.cursor.rowcount = 0
        mock_db.return_value.__enter__.return_value = mock_conn

        with patch('builtins.input', return_value='1'):
            vote_president('VOTER1')

        queries = [c.args[0] for c in mock_conn.execute_query.call_args_list]
        assert not any('INSERT INTO votes' in q for q in queries)

    @patch('voting.bc.get_presidential_election_id', return_value=None)
    def test_vote_president_no_election(self, mock_pres_id):
        from voting import vote_president

        vote_president('VOTER1')
