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
    missing = []
    for var, desc in REQUIRED_ENV_VARS:
        if not os.getenv(var):
            missing.append(f"  {var} ({desc})")
    if missing:
        print("ERROR: Missing required environment variables in .env:")
        print("\n".join(missing))
        print("\nPlease check your .env file.")
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
    AUTH_SESSION['logged_in'] = False
    AUTH_SESSION['username'] = None
    AUTH_SESSION['role'] = None
    print("Logged out.")


def is_admin_logged_in():
    return AUTH_SESSION['logged_in']
