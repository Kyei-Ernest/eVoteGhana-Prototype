import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch


class TestTransitionRules:
    def test_forward_single_step_allowed(self):
        from election import _transition_allowed

        assert _transition_allowed('nomination', 'campaigning') is True
        assert _transition_allowed('campaigning', 'voting') is True
        assert _transition_allowed('voting', 'results') is True
        assert _transition_allowed('results', 'closed') is True

    def test_forward_multi_step_allowed(self):
        from election import _transition_allowed

        assert _transition_allowed('nomination', 'voting') is True

    def test_backward_forbidden(self):
        from election import _transition_allowed

        assert _transition_allowed('campaigning', 'nomination') is False
        assert _transition_allowed('voting', 'campaigning') is False
        assert _transition_allowed('results', 'voting') is False
        assert _transition_allowed('closed', 'nomination') is False

    def test_close_requires_results_phase(self):
        from election import _transition_allowed

        assert _transition_allowed('nomination', 'closed') is False
        assert _transition_allowed('voting', 'closed') is False
        assert _transition_allowed('results', 'closed') is True

    def test_scheduled_counts_as_first_phase(self):
        from election import _transition_allowed

        assert _transition_allowed('scheduled', 'nomination') is True
        assert _transition_allowed('scheduled', 'voting') is True
        assert _transition_allowed('scheduled', 'closed') is False

    def test_same_phase_forbidden(self):
        from election import _transition_allowed

        assert _transition_allowed('voting', 'voting') is False


class TestMajorityRule:
    def test_majority_achieved(self):
        from election import check_50_percent_plus_one

        assert check_50_percent_plus_one(100, 51) is True

    def test_exact_half_not_enough(self):
        """Constitutional majority means strictly more than half."""
        from election import check_50_percent_plus_one

        assert check_50_percent_plus_one(100, 50) is False

    def test_no_votes_no_majority(self):
        from election import check_50_percent_plus_one

        assert check_50_percent_plus_one(0, 0) is False


class TestRunoffWorkflow:
    @patch('election.DatabaseManager')
    def test_top_two_none_when_majority_winner(self, mock_db):
        from election import presidential_top_two

        conn = MagicMock()
        conn.fetch_one.return_value = (100,)  # total votes
        conn.fetch_all.return_value = [(1, 60, 'Winner', 1), (2, 40, 'Runner', 2)]
        mock_db.return_value.__enter__.return_value = conn

        assert presidential_top_two(1) is None

    @patch('election.DatabaseManager')
    def test_top_two_returned_when_runoff_needed(self, mock_db):
        from election import presidential_top_two

        conn = MagicMock()
        conn.fetch_one.return_value = (100,)
        conn.fetch_all.return_value = [(1, 45, 'A', 1), (2, 40, 'B', 2)]
        mock_db.return_value.__enter__.return_value = conn

        top_two = presidential_top_two(1)
        assert top_two is not None
        assert len(top_two) == 2
        assert top_two[0][2] == 'A'
        assert top_two[1][2] == 'B'

    @patch('audit_log.log_action')
    @patch('election.presidential_top_two')
    @patch('election.DatabaseManager')
    def test_create_runoff_seeds_two_candidates(self, mock_db, mock_top_two, mock_log):
        from election import create_runoff_election

        mock_top_two.return_value = [(1, 45, 'A', 3), (2, 40, 'B', None)]

        conn = MagicMock()
        conn.fetch_one.return_value = ('General Election',)
        conn.cursor.lastrowid = 42
        mock_db.return_value.__enter__.return_value = conn

        runoff_id = create_runoff_election(7)
        assert runoff_id == 42

        queries = [c.args[0] for c in conn.execute_query.call_args_list]
        inserts = [q for q in queries if 'INSERT INTO candidates' in q]
        assert len(inserts) == 2

    @patch('election.DatabaseManager')
    def test_transition_denial_logged(self, mock_db):
        from election import transition_phase

        with patch('election.get_current_phase', return_value='nomination'), patch('audit_log.log_action') as mock_log:
            result = transition_phase(5, 'closed')

        assert result is False
        actions = [c.args[0] for c in mock_log.call_args_list]
        assert 'phase_transition_denied' in actions
