import os
import sys
import getpass

AUTH_SESSION = {'logged_in': False, 'username': None, 'role': None}

REQUIRED_ENV_VARS = [
    ('DB_HOST', 'Database host'),
    ('DB_USER', 'Database user'),
    ('DB_PASSWORD', 'Database password'),
    ('DB_NAME_MAIN', 'Main database name'),
]

SECRET_ENV_VARS = [
    'DB_PASSWORD',
    'HMAC_SECRET_KEY',
]


def validate_config():
    """Check that all required environment variables are set and valid; exit with instructions if not."""
    missing = []
    for var, desc in REQUIRED_ENV_VARS:
        if not os.getenv(var):
            missing.append(f"  {var} ({desc})")
    if missing:
        print("\n" + "=" * 60)
        print("  eVoteGhana - First Time Setup Required")
        print("=" * 60)
        print("\nMissing environment variables:")
        print("\n".join(missing))
        print("\nTo get started:")
        print("  1. Copy .env.example to .env:")
        print("     cp .env.example .env")
        print("  2. Edit .env with your MySQL credentials")
        print("  3. Run the schema setup:")
        print("     python3 schema.py")
        print("  4. Start the application:")
        print("     python3 main.py")
        print("\nSee README.md for detailed instructions.")
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
        print("WARNING: HMAC_SECRET_KEY is using the default value. Set a strong random key in production.")

    print("Configuration validated.\n")
    return True


def require_admin():
    """Authenticate the user as an admin if not already logged in; return True on success."""
    if not AUTH_SESSION['logged_in']:
        print("\nAdmin authentication required.")
        username = input("Admin username: ")
        from database import DatabaseManager
        import bcrypt
        with DatabaseManager() as db:
            db.execute_query("SELECT password_hash, role FROM admins WHERE username = %s", (username,))
            row = db.fetch_one()
            if not row:
                print("Invalid credentials.")
                return False
            stored_hash, role = row
            password = getpass.getpass("Admin password: ")
            if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
                AUTH_SESSION['logged_in'] = True
                AUTH_SESSION['username'] = username
                AUTH_SESSION['role'] = role
                print(f"Logged in as {username} ({role}).")
                return True
            else:
                print("Invalid credentials.")
                return False
    return True


def logout_admin():
    """Clear the current admin session."""
    AUTH_SESSION['logged_in'] = False
    AUTH_SESSION['username'] = None
    AUTH_SESSION['role'] = None
    print("Logged out.")


def is_admin_logged_in():
    """Return whether an admin is currently authenticated."""
    return AUTH_SESSION['logged_in']
