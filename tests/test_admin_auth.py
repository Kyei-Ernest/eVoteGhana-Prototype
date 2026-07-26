import sys
import os
import time
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAdminAuthSession:
    def test_session_expired_after_timeout(self):
        from admin_auth import AUTH_SESSION, _session_expired
        AUTH_SESSION['logged_in'] = True
        AUTH_SESSION['login_time'] = time.time() - 2000
        assert _session_expired() is True

    def test_session_not_expired_within_window(self):
        from admin_auth import AUTH_SESSION, _session_expired
        AUTH_SESSION['logged_in'] = True
        AUTH_SESSION['login_time'] = time.time() - 100
        assert _session_expired() is False

    def test_not_logged_in_is_expired(self):
        from admin_auth import AUTH_SESSION, _session_expired
        AUTH_SESSION['logged_in'] = False
        assert _session_expired() is True

    def test_logout_clears_timestamp(self):
        from admin_auth import AUTH_SESSION, logout_admin
        AUTH_SESSION['logged_in'] = True
        AUTH_SESSION['login_time'] = time.time()
        logout_admin()
        assert AUTH_SESSION['logged_in'] is False
        assert AUTH_SESSION['login_time'] == 0.0


class TestAdminAuthRateLimiter:
    def test_admin_auth_limiter_exists(self):
        from admin_auth import admin_auth_limiter
        assert admin_auth_limiter.is_allowed('test_admin') is True

    def test_admin_auth_rate_limiter_blocks(self):
        from admin_auth import admin_auth_limiter
        for _ in range(5):
            admin_auth_limiter.is_allowed('blocked_admin')
        assert admin_auth_limiter.is_allowed('blocked_admin') is False


class TestAdminLogin:
    @patch('database.DatabaseManager')
    def test_login_success(self, mock_db):
        import bcrypt
        from admin_auth import require_admin, AUTH_SESSION

        password = 'test_pass'
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        mock_instance = MagicMock()
        mock_instance.fetch_one.return_value = (hashed, 'admin')
        mock_db.return_value.__enter__.return_value = mock_instance

        AUTH_SESSION['logged_in'] = False

        with patch('builtins.input', return_value='test_admin'), \
             patch('getpass.getpass', return_value=password):
            result = require_admin()

        assert result is True
        assert AUTH_SESSION['logged_in'] is True
        assert AUTH_SESSION['username'] == 'test_admin'

    @patch('database.DatabaseManager')
    def test_login_failure_wrong_password(self, mock_db):
        import bcrypt
        from admin_auth import require_admin, AUTH_SESSION

        hashed = bcrypt.hashpw(b'correct_password', bcrypt.gensalt()).decode('utf-8')

        mock_instance = MagicMock()
        mock_instance.fetch_one.return_value = (hashed, 'admin')
        mock_db.return_value.__enter__.return_value = mock_instance

        AUTH_SESSION['logged_in'] = False

        with patch('builtins.input', return_value='test_admin'), \
             patch('getpass.getpass', return_value='wrong_password'):
            result = require_admin()

        assert result is False
        assert AUTH_SESSION['logged_in'] is False

    @patch('database.DatabaseManager')
    def test_login_user_not_found(self, mock_db):
        from admin_auth import require_admin, AUTH_SESSION

        mock_instance = MagicMock()
        mock_instance.fetch_one.return_value = None
        mock_db.return_value.__enter__.return_value = mock_instance

        AUTH_SESSION['logged_in'] = False

        with patch('builtins.input', return_value='unknown_user'), \
             patch('getpass.getpass', return_value='any_pass'):
            result = require_admin()

        assert result is False
