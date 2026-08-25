import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch


class TestDatabaseRateLimiter:
    def _conn_with_window(self, hits=0, age=0):
        conn = MagicMock()
        conn.fetch_one.return_value = (hits, age) if hits is not None else None
        return conn

    @patch('database.DatabaseManager')
    def test_first_attempt_allowed_and_recorded(self, mock_db):
        from rate_limiter import DatabaseRateLimiter

        conn = self._conn_with_window(hits=None)
        conn.fetch_one.return_value = None
        mock_db.return_value.__enter__.return_value = conn

        rl = DatabaseRateLimiter(max_attempts=3, window_seconds=60)
        assert rl.is_allowed('voter:x') is True
        inserts = [c.args[0] for c in conn.execute_query.call_args_list if 'INSERT' in c.args[0]]
        assert len(inserts) == 1

    @patch('database.DatabaseManager')
    def test_blocks_when_hits_exhausted(self, mock_db):
        from rate_limiter import DatabaseRateLimiter

        conn = self._conn_with_window(hits=3, age=10)
        mock_db.return_value.__enter__.return_value = conn

        rl = DatabaseRateLimiter(max_attempts=3, window_seconds=60)
        assert rl.is_allowed('voter:x') is False

    @patch('database.DatabaseManager')
    def test_expired_window_resets(self, mock_db):
        from rate_limiter import DatabaseRateLimiter

        conn = self._conn_with_window(hits=3, age=61)
        mock_db.return_value.__enter__.return_value = conn

        rl = DatabaseRateLimiter(max_attempts=3, window_seconds=60)
        assert rl.is_allowed('voter:x') is True
        resets = [c.args[0] for c in conn.execute_query.call_args_list if 'SET hits = 1' in c.args[0]]
        assert len(resets) == 1

    @patch('database.DatabaseManager')
    def test_fails_open_on_database_error(self, mock_db):
        from rate_limiter import DatabaseRateLimiter

        conn = MagicMock()
        conn.execute_query.side_effect = RuntimeError('db down')
        mock_db.return_value.__enter__.return_value = conn

        rl = DatabaseRateLimiter(max_attempts=3, window_seconds=60)
        assert rl.is_allowed('voter:x') is True

    @patch('database.DatabaseManager')
    def test_remaining_counts_down(self, mock_db):
        from rate_limiter import DatabaseRateLimiter

        conn = self._conn_with_window(hits=2, age=5)
        mock_db.return_value.__enter__.return_value = conn

        rl = DatabaseRateLimiter(max_attempts=5, window_seconds=60)
        assert rl.remaining_attempts('voter:x') == 3
