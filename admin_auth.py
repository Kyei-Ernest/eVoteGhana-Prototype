import getpass
import os
import sys
import time

from rate_limiter import RateLimiter

AUTH_SESSION: dict = {'logged_in': False, 'username': None, 'role': None, 'login_time': 0.0}

SESSION_TIMEOUT_SECONDS: int = 1800

admin_auth_limiter = RateLimiter(max_attempts=5, window_seconds=300)

REQUIRED_ENV_VARS: list[tuple[str, str]] = [
    ('DB_HOST', 'Database host'),
    ('DB_USER', 'Database user'),
    ('DB_PASSWORD', 'Database password'),
    ('DB_NAME_MAIN', 'Main database name'),
]

SECRET_ENV_VARS: list[str] = [
    'DB_PASSWORD',
    'HMAC_SECRET_KEY',
]


def _session_expired() -> bool:
    if not AUTH_SESSION['logged_in']:
        return True
    elapsed = time.time() - AUTH_SESSION['login_time']
    return elapsed > SESSION_TIMEOUT_SECONDS


def validate_config() -> bool:
    missing = []
    for var, desc in REQUIRED_ENV_VARS:
        if not os.getenv(var):
            missing.append(f'  {var} ({desc})')
    if missing:
        print('\n' + '=' * 60)
        print('  eVoteGhana - First Time Setup Required')
        print('=' * 60)
        print('\nMissing environment variables:')
        print('\n'.join(missing))
        print('\nTo get started:')
        print('  1. Copy .env.example to .env:')
        print('     cp .env.example .env')
        print('  2. Edit .env with your MySQL credentials')
        print('  3. Run the schema setup:')
        print('     python3 schema.py')
        print('  4. Start the application:')
        print('     python3 main.py')
        print('\nSee README.md for detailed instructions.')
        sys.exit(1)

    port = os.getenv('DB_PORT', '3306')
    try:
        int(port)
    except ValueError:
        print(f"ERROR: DB_PORT must be a number, got '{port}'")
        sys.exit(1)

    lang = os.getenv('LANGUAGE', 'en')
    if lang not in ('en', 'tw', 'ee'):
        print(f"WARNING: Unknown LANGUAGE '{lang}', falling back to English")

    hmac_key = os.getenv('HMAC_SECRET_KEY', '')
    if not hmac_key or hmac_key == 'change-this-to-a-secure-random-key-in-production':
        print('WARNING: HMAC_SECRET_KEY is using the default value. Set a strong random key in production.')

    print('Configuration validated.\n')
    return True


def require_admin() -> bool:
    if AUTH_SESSION['logged_in'] and not _session_expired():
        return True

    if AUTH_SESSION['logged_in'] and _session_expired():
        print('Session expired. Please log in again.')
        AUTH_SESSION['logged_in'] = False

    print('\nAdmin authentication required.')
    username = input('Admin username: ')

    if not admin_auth_limiter.is_allowed(username):
        print('Too many login attempts. Try again later.')
        return False

    import bcrypt

    from database import DatabaseManager

    with DatabaseManager() as db:
        db.execute_query('SELECT password_hash, role FROM admins WHERE username = %s', (username,))
        row = db.fetch_one()
        if not row:
            print('Invalid credentials.')
            return False
        stored_hash, role = row
        password = getpass.getpass('Admin password: ')
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
            AUTH_SESSION['logged_in'] = True
            AUTH_SESSION['username'] = username
            AUTH_SESSION['role'] = role
            AUTH_SESSION['login_time'] = time.time()
            print(f'Logged in as {username} ({role}).')
            return True
        else:
            print('Invalid credentials.')
            return False


def logout_admin() -> None:
    AUTH_SESSION['logged_in'] = False
    AUTH_SESSION['username'] = None
    AUTH_SESSION['role'] = None
    AUTH_SESSION['login_time'] = 0.0
    print('Logged out.')


def is_admin_logged_in() -> bool:
    if AUTH_SESSION['logged_in'] and _session_expired():
        AUTH_SESSION['logged_in'] = False
        return False
    return AUTH_SESSION['logged_in']
