import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestEmailValidation:
    def test_valid_email(self):
        from validation import is_valid_email

        assert is_valid_email('user@example.com') is True
        assert is_valid_email('user.name+tag@example.co.uk') is True
        assert is_valid_email('test@example.io') is True

    def test_invalid_email(self):
        from validation import is_valid_email

        assert is_valid_email('not-an-email') is False
        assert is_valid_email('@example.com') is False
        assert is_valid_email('user@') is False
        assert is_valid_email('') is False


class TestGhanaCardValidation:
    def test_valid_ghana_card(self):
        from validation import is_valid_ghana_card

        assert is_valid_ghana_card('GHA-ABCD1234EF') is True
        assert is_valid_ghana_card('GHA-0123456789') is True
        assert is_valid_ghana_card('gha-ABCD1234EF') is True

    def test_invalid_ghana_card(self):
        from validation import is_valid_ghana_card

        assert is_valid_ghana_card('') is False
        assert is_valid_ghana_card('GHA-123') is False
        assert is_valid_ghana_card('ABC-1234567890') is False
        assert is_valid_ghana_card('GHA-ABCD1234EFG') is False


class TestContactValidation:
    def test_valid_contact(self):
        from validation import is_valid_contact

        assert is_valid_contact('0241234567') is True
        assert is_valid_contact('0551234567') is True

    def test_invalid_contact(self):
        from validation import is_valid_contact

        assert is_valid_contact('') is False
        assert is_valid_contact('1234567890') is False
        assert is_valid_contact('024123456') is False
        assert is_valid_contact('02412345678') is False
        assert is_valid_contact('abc1234567') is False


class TestPasswordStrength:
    def test_valid_password(self):
        from validation import validate_password_strength

        valid, msg = validate_password_strength('ValidP@ss1')
        assert valid is True
        assert msg == ''

    def test_too_short(self):
        from validation import validate_password_strength

        valid, msg = validate_password_strength('Sh0rt!')
        assert valid is False
        assert '10 characters' in msg

    def test_no_uppercase(self):
        from validation import validate_password_strength

        valid, msg = validate_password_strength('lowercasep@ss1')
        assert valid is False
        assert 'uppercase' in msg

    def test_no_lowercase(self):
        from validation import validate_password_strength

        valid, msg = validate_password_strength('UPPERCASEP@SS1')
        assert valid is False
        assert 'lowercase' in msg

    def test_no_digit(self):
        from validation import validate_password_strength

        valid, msg = validate_password_strength('NoDigitsP@ss')
        assert valid is False
        assert 'digit' in msg

    def test_no_special_char(self):
        from validation import validate_password_strength

        valid, msg = validate_password_strength('NoSpecialChar1')
        assert valid is False
        assert 'special character' in msg
