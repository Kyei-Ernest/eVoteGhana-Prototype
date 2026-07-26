import os
import subprocess
from datetime import datetime
from config import Config
from audit_log import log_action


BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')


def _ensure_backup_dir() -> None:
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _build_env() -> dict:
    env = os.environ.copy()
    env['MYSQL_PWD'] = Config.DB_PASSWORD
    return env


def backup_database() -> None:
    _ensure_backup_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"evote_backup_{timestamp}.sql"
    filepath = os.path.join(BACKUP_DIR, filename)

    try:
        cmd = [
            'mysqldump',
            f'--host={Config.DB_HOST}',
            f'--user={Config.DB_USER}',
            f'--port={Config.DB_PORT}',
            Config.DB_NAME_MAIN,
        ]
        with open(filepath, 'w') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True, env=_build_env())

        if result.returncode == 0:
            size = os.path.getsize(filepath)
            log_action('backup_created', 'database', filename, f"Size: {size} bytes")
            print(f"Backup saved: {filepath} ({size} bytes)")
        else:
            print(f"Backup failed: {result.stderr}")
    except FileNotFoundError:
        print("Error: mysqldump not found. Install MySQL client tools.")
    except Exception as e:
        print(f"Backup error: {e}")


def restore_database() -> None:
    _ensure_backup_dir()
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.sql')], reverse=True)

    if not backups:
        print("No backups found in backups/ directory.")
        return

    print("\nAvailable backups:")
    for i, b in enumerate(backups, 1):
        size = os.path.getsize(os.path.join(BACKUP_DIR, b))
        print(f"{i}. {b} ({size} bytes)")

    try:
        choice = int(input("\nEnter backup number to restore (0 to cancel): "))
        if choice == 0:
            return
        if choice < 1 or choice > len(backups):
            print("Invalid choice.")
            return

        filename = backups[choice - 1]
        filepath = os.path.join(BACKUP_DIR, filename)

        confirm = input(f"Restore {filename}? This will overwrite the current database. (yes/no): ")
        if confirm.lower() != 'yes':
            print("Restore cancelled.")
            return

        cmd = [
            'mysql',
            f'--host={Config.DB_HOST}',
            f'--user={Config.DB_USER}',
            f'--port={Config.DB_PORT}',
            Config.DB_NAME_MAIN,
        ]
        with open(filepath, 'r') as f:
            result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, text=True, env=_build_env())

        if result.returncode == 0:
            log_action('restore_completed', 'database', filename, "Restored from backup")
            print(f"Database restored from {filename}.")
        else:
            print(f"Restore failed: {result.stderr}")
    except ValueError:
        print("Invalid input.")
    except Exception as e:
        print(f"Restore error: {e}")
