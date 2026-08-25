import re

EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
GHANA_CARD_RE = re.compile(r'^GHA-[A-Z0-9]{10}$', re.IGNORECASE)
CONTACT_RE = re.compile(r'^0\d{9}$')

MIN_PASSWORD_LENGTH = 10


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email.strip()))


def is_valid_ghana_card(personal_id: str) -> bool:
    return bool(GHANA_CARD_RE.match(personal_id.strip()))


def is_valid_contact(contact: str) -> bool:
    return bool(CONTACT_RE.match(contact.strip()))


def validate_password_strength(password: str) -> tuple[bool, str]:
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, 'Password must be at least 10 characters.'
    if not any(c.isupper() for c in password):
        return False, 'Password must contain at least one uppercase letter.'
    if not any(c.islower() for c in password):
        return False, 'Password must contain at least one lowercase letter.'
    if not any(c.isdigit() for c in password):
        return False, 'Password must contain at least one digit.'
    if not any(c in '!@#$%^&*()-_=+[]{}|;:,.<>?/~`' for c in password):
        return False, 'Password must contain at least one special character.'
    return True, ''
