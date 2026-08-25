import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMysqlValueChecker:
    def test_validate_table_valid(self):
        from mysql_value_checker import _validate_table

        assert _validate_table('voterinfo') == 'voterinfo'
        assert _validate_table('candidates') == 'candidates'

    def test_validate_table_invalid(self):
        from mysql_value_checker import _validate_table

        with pytest.raises(ValueError):
            _validate_table('nonexistent_table')

    def test_validate_table_sql_injection_attempt(self):
        from mysql_value_checker import _validate_table

        with pytest.raises(ValueError):
            _validate_table('voterinfo; DROP TABLE voterinfo')
        with pytest.raises(ValueError):
            _validate_table('voterinfo --')
        with pytest.raises(ValueError):
            _validate_table("voterinfo' OR '1'='1")


class TestMysqlDelete:
    def test_validate_table_valid(self):
        from mysql_delete import _validate_table

        assert _validate_table('voterinfo') == 'voterinfo'
        assert _validate_table('parties') == 'parties'

    def test_validate_table_invalid(self):
        from mysql_delete import _validate_table

        with pytest.raises(ValueError):
            _validate_table('information_schema')


class TestI18n:
    def test_english(self):
        os.environ['LANGUAGE'] = 'en'
        import i18n

        i18n.LANGUAGE = 'en'
        from i18n import _

        assert _('welcome') == '=== GHANA VOTING SYSTEM MAIN MENU ==='

    def test_unknown_language_falls_back_to_english(self):
        os.environ['LANGUAGE'] = 'xx'
        import i18n

        i18n.LANGUAGE = 'xx'
        from i18n import _

        assert _('welcome') == '=== GHANA VOTING SYSTEM MAIN MENU ==='

    def test_twi_translation_exists(self):
        os.environ['LANGUAGE'] = 'tw'
        import i18n

        i18n.LANGUAGE = 'tw'
        from i18n import _

        assert _('cast_vote') == '2. To Ba'

    def test_unknown_key_returns_key(self):
        os.environ['LANGUAGE'] = 'en'
        import i18n

        i18n.LANGUAGE = 'en'
        from i18n import _

        assert _('nonexistent_key') == 'nonexistent_key'
