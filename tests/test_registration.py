import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRegisterVoter:
    def test_age_calculation(self):
        from Registration import RegisterVoter
        voter = RegisterVoter(
            voter_id='TESTID', name='Test', contact='0241234567',
            email='test@example.com', date_of_birth='15/03/2000',
            personal_id='GHA-ABCD1234EF', occupation='Engineer',
            constituency_id=1, polling_station_id=1,
            password='ValidP@ss1', conf_pass='ValidP@ss1'
        )
        age_val = voter.calculate_age()
        assert age_val >= 24

    def test_underage_rejected(self):
        from Registration import RegisterVoter
        voter = RegisterVoter(
            voter_id='TESTID', name='Test', contact='0241234567',
            email='test@example.com', date_of_birth='15/03/2015',
            personal_id='GHA-ABCD1234EF', occupation='Student',
            constituency_id=1, polling_station_id=1,
            password='ValidP@ss1', conf_pass='ValidP@ss1'
        )
        result = voter.verification()
        assert result is False

    @patch('Registration.vc.check_value_exists', return_value=True)
    def test_duplicate_id_regenerates(self, mock_check):
        from Registration import RegisterVoter
        voter = RegisterVoter(
            voter_id='EXISTING', name='Test', contact='0241234567',
            email='test@example.com', date_of_birth='15/03/2000',
            personal_id='GHA-ABCD1234EF', occupation='Engineer',
            constituency_id=1, polling_station_id=1,
            password='ValidP@ss1', conf_pass='ValidP@ss1'
        )
        original_id = voter.id
        with patch('Registration.vc.check_value_exists') as mock_exists:
            mock_exists.side_effect = [True, False, True, True]
            with patch('builtins.input', return_value='Test'):
                with patch('getpass.getpass', return_value='ValidP@ss1'):
                    with patch.object(voter, 'full_info', return_value=True):
                        voter.verification()

        assert voter.id != original_id
        assert len(voter.id) == 8

    @patch('Registration.vc.check_value_exists', return_value=False)
    @patch('Registration.DatabaseManager')
    def test_successful_registration(self, mock_db, mock_check):
        from Registration import RegisterVoter
        voter = RegisterVoter(
            voter_id='NEWVOTER', name='Test User', contact='0241234567',
            email='test@example.com', date_of_birth='15/03/2000',
            personal_id='GHA-ABCD1234EF', occupation='Engineer',
            constituency_id=1, polling_station_id=1,
            password='ValidP@ss1', conf_pass='ValidP@ss1'
        )
        mock_conn = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_conn

        result = voter.full_info()
        assert result is True


class TestRegistrationFunctions:
    def test_list_constituencies_empty(self):
        from Registration import list_constituencies
        with patch('Registration.DatabaseManager') as mock_db:
            mock_conn = MagicMock()
            mock_conn.fetch_all.return_value = []
            mock_db.return_value.__enter__.return_value = mock_conn
            result = list_constituencies()
            assert result == []

    def test_list_polling_stations(self):
        from Registration import list_polling_stations
        with patch('Registration.DatabaseManager') as mock_db:
            mock_conn = MagicMock()
            mock_conn.fetch_all.return_value = [(1, 'Station A', 'SA-01', 'Constituency X')]
            mock_db.return_value.__enter__.return_value = mock_conn
            result = list_polling_stations()
            assert len(result) == 1
