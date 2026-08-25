"""Non-interactive first-run bootstrap for the web app.

Creates the database and tables, seeds the 16 regions, and creates the initial
admin account from ADMIN_USERNAME / ADMIN_PASSWORD when the admins table is empty.
Safe to run on every startup (all DDL is idempotent).
"""

import fcntl
import logging
import os
import re
import time
from contextlib import contextmanager

import bcrypt
import mysql.connector

import schema as schema_module
from config import Config
from database import DatabaseManager

MIN_ADMIN_PASSWORD_LENGTH = 8

logger = logging.getLogger('evote.bootstrap')

# Keep DDL in dependency order so foreign keys resolve.
DDL_STATEMENTS = [
    schema_module.CREATE_REGIONS,
    schema_module.CREATE_CONSTITUENCIES,
    schema_module.CREATE_POLLING_STATIONS,
    schema_module.CREATE_PARTIES,
    schema_module.CREATE_ELECTIONS,
    schema_module.CREATE_CANDIDATES,
    schema_module.CREATE_VOTERINFO,
    schema_module.CREATE_PASS_TABLE,
    schema_module.CREATE_VOTES,
    schema_module.CREATE_ADMINS,
    schema_module.CREATE_AUDIT_LOG,
    schema_module.CREATE_RATE_LIMIT_BUCKETS,
]

_DB_NAME_RE = re.compile(r'^[A-Za-z0-9_]+$')


def ensure_database() -> None:
    """Create the main database if it does not exist."""
    dbname = Config.DB_NAME_MAIN
    if not _DB_NAME_RE.match(dbname):
        raise ValueError(f'Invalid DB_NAME_MAIN: {dbname!r}')
    conn = mysql.connector.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        port=Config.DB_PORT,
    )
    try:
        cursor = conn.cursor()
        cursor.execute(f'CREATE DATABASE IF NOT EXISTS `{dbname}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def _ensure_columns(db: DatabaseManager, table: str, columns: list[tuple[str, str]]) -> None:
    """Add missing columns to an existing table (MySQL 8 lacks ADD COLUMN IF NOT EXISTS)."""
    for col, ddl in columns:
        db.execute_query(
            'SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() '
            'AND table_name = %s AND column_name = %s',
            (table, col),
        )
        if db.fetch_one()[0] == 0:
            db.execute_query(f'ALTER TABLE `{table}` ADD COLUMN `{col}` {ddl} NULL')
            logger.info('Added missing column %s.%s', table, col)


def ensure_schema() -> None:
    """Create all tables and converge any older deployment onto the current model."""
    with DatabaseManager() as db:
        for ddl in DDL_STATEMENTS:
            db.execute_query(ddl)
        db.execute_query(schema_module.SEED_REGIONS)
        # Data migrations run while immutability triggers are absent because
        # several of them need to UPDATE historical rows.
        db.execute_query('DROP TRIGGER IF EXISTS audit_log_no_update')
        db.execute_query('DROP TRIGGER IF EXISTS audit_log_no_delete')
        _migrate_legacy_ballot_slots(db)
        _ensure_votes_key_version(db)
        _migrate_votes_drop_voter_link(db)
        _migrate_admin_totp_columns(db)
        _ensure_audit_chain_columns_and_backfill(db)
        _ensure_unique_personal_id(db)
        _ensure_audit_immutability(db)
    logger.info('Schema ensured.')


def _table_has_column(db: DatabaseManager, table: str, column: str) -> bool:
    db.execute_query(
        'SELECT COUNT(*) FROM information_schema.columns '
        'WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s',
        (table, column),
    )
    return db.fetch_one()[0] > 0


def _migrate_legacy_ballot_slots(db: DatabaseManager) -> None:
    """Convert candidate storing vote columns into secrecy preserving flags.

    Deployments from earlier prototypes recorded the chosen candidate id on the
    voter roll itself, which is the opposite of a secret ballot. The choice
    linkage is destroyed after converting it into used slot flags; run a backup
    before upgrading a database containing real history.
    """
    legacy_present = _table_has_column(db, 'voterinfo', 'mp_vote') or _table_has_column(
        db, 'voterinfo', 'president_vote'
    )
    if not legacy_present and _table_has_column(db, 'voterinfo', 'mp_voted'):
        return
    for col in ('mp_voted', 'president_voted'):
        if not _table_has_column(db, 'voterinfo', col):
            db.execute_query(f'ALTER TABLE voterinfo ADD COLUMN {col} BOOLEAN NOT NULL DEFAULT FALSE')
    if _table_has_column(db, 'voterinfo', 'mp_vote'):
        db.execute_query('UPDATE voterinfo SET mp_voted = 1 WHERE mp_vote IS NOT NULL')
    if _table_has_column(db, 'voterinfo', 'president_vote'):
        db.execute_query('UPDATE voterinfo SET president_voted = 1 WHERE president_vote IS NOT NULL')
    for col in ('mp_vote', 'president_vote'):
        if _table_has_column(db, 'voterinfo', col):
            db.execute_query(f'ALTER TABLE voterinfo DROP COLUMN {col}')
    logger.warning(
        'Migrated voter roll to boolean ballot slots; per voter choice linkage was removed for ballot secrecy.'
    )


def _ensure_votes_key_version(db: DatabaseManager) -> None:
    if not _table_has_column(db, 'votes', 'key_version'):
        db.execute_query("ALTER TABLE votes ADD COLUMN key_version VARCHAR(8) NOT NULL DEFAULT 'k1'")
        logger.info('Added key_version to votes for signing key rotation.')


def _migrate_votes_drop_voter_link(db: DatabaseManager) -> None:
    """Remove the voter identity column from stored ballots on legacy databases.

    This permanently destroys the ability to map historical ballots to voters;
    that destruction is the privacy remediation, not an accident of it.
    """
    if not _table_has_column(db, 'votes', 'voter_id'):
        return
    db.execute_query(
        'SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE '
        "WHERE table_schema = DATABASE() AND table_name = 'votes' AND column_name = 'voter_id' "
        'AND referenced_column_name IS NOT NULL LIMIT 1'
    )
    row = db.fetch_one()
    if row:
        db.execute_query(f'ALTER TABLE votes DROP FOREIGN KEY `{row[0]}`')
    db.execute_query('ALTER TABLE votes DROP COLUMN voter_id')
    logger.warning('Dropped votes.voter_id: ballots are now anonymous at storage level.')


def _migrate_admin_totp_columns(db: DatabaseManager) -> None:
    for col, ddl in (('totp_secret', 'VARCHAR(32) NULL'), ('totp_enabled', 'BOOLEAN NOT NULL DEFAULT FALSE')):
        if not _table_has_column(db, 'admins', col):
            db.execute_query(f'ALTER TABLE admins ADD COLUMN {col} {ddl}')


def _ensure_audit_chain_columns_and_backfill(db: DatabaseManager) -> None:
    """Add chain columns when missing and link every existing unchained entry."""
    changed = False
    if not _table_has_column(db, 'audit_log', 'prev_hash'):
        db.execute_query('ALTER TABLE audit_log ADD COLUMN prev_hash CHAR(64) NOT NULL')
        changed = True
    if not _table_has_column(db, 'audit_log', 'entry_hash'):
        db.execute_query('ALTER TABLE audit_log ADD COLUMN entry_hash CHAR(64) NOT NULL')
        changed = True

    from audit_log import GENESIS_HASH, _entry_hash

    db.execute_query('SELECT id, action, table_name, record_id, details, actor, created_at FROM audit_log ORDER BY id')
    rows = db.fetch_all()
    needs_backfill = changed or any(r[6] is None for r in rows)
    if not needs_backfill:
        return
    prev = GENESIS_HASH
    for entry_id, action, table_name, record_id, details, actor, created_at in rows:
        ts = created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at or '')
        digest = _entry_hash(prev, action, table_name, str(record_id), str(details or ''), str(actor or ''), ts)
        db.execute_query(
            'UPDATE audit_log SET prev_hash = %s, entry_hash = %s, created_at = %s WHERE id = %s',
            (prev, digest, ts, entry_id),
        )
        prev = digest
    logger.info('Audit chain backfilled over %d entries.', len(rows))


def _ensure_unique_personal_id(db: DatabaseManager) -> None:
    """Add the unique index on voterinfo.personal_id to databases created before it existed.

    Duplicate Ghana Card IDs are then impossible at the storage layer. Existing
    duplicates make index creation fail; that failure is logged loudly so an
    operator can de-duplicate before restarting.
    """
    db.execute_query(
        'SELECT COUNT(*) FROM information_schema.statistics '
        'WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s',
        ('voterinfo', 'uq_voterinfo_personal_id'),
    )
    if db.fetch_one()[0] == 0:
        try:
            db.execute_query('ALTER TABLE voterinfo ADD UNIQUE INDEX uq_voterinfo_personal_id (personal_id)')
            logger.info('Added unique index uq_voterinfo_personal_id on voterinfo.')
        except Exception as exc:  # noqa: BLE001
            logger.error('Could not add unique personal_id index (duplicate Ghana Cards present?): %s', exc)
            raise


def _ensure_audit_immutability(db: DatabaseManager) -> None:
    """(Re)install triggers that make the audit log physically append-only."""
    for drop_sql, trigger_ddl in zip(schema_module.APPLY_TRIGGER_SQL, schema_module.AUDIT_IMMUTABILITY_TRIGGERS):
        db.execute_query(drop_sql)
        db.execute_query(trigger_ddl)


def ensure_admin() -> None:
    """Create the initial admin from env vars when the admins table is empty."""
    username = os.getenv('ADMIN_USERNAME', '').strip()
    password = os.getenv('ADMIN_PASSWORD', '').strip()

    with DatabaseManager() as db:
        db.execute_query('SELECT COUNT(*) FROM admins')
        if db.fetch_one()[0] > 0:
            return
        if not username or not password:
            logger.warning(
                'admins table is empty but ADMIN_USERNAME/ADMIN_PASSWORD are not set; '
                'no admin account created. Set them in .env and restart.'
            )
            return
        if len(password) < MIN_ADMIN_PASSWORD_LENGTH:
            logger.warning(
                'ADMIN_PASSWORD is shorter than %d characters; admin account not created.',
                MIN_ADMIN_PASSWORD_LENGTH,
            )
            return
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        db.execute_query(
            "INSERT INTO admins(username, password_hash, role) VALUES (%s, %s, 'super_admin')",
            (username, hashed),
        )
        logger.info('Created initial admin account %r.', username)


def _run() -> None:
    max_retries = int(os.getenv('DB_CONNECT_RETRIES', '30'))
    delay = float(os.getenv('DB_CONNECT_RETRY_DELAY', '2'))
    attempt = 0
    while True:
        try:
            ensure_database()
            ensure_schema()
            ensure_admin()
            return
        except Exception as exc:  # noqa: BLE001 - startup must not crash the app
            attempt += 1
            if attempt >= max_retries:
                logger.error('Bootstrap failed after %d attempts: %s', attempt, exc)
                return
            logger.warning('Bootstrap attempt %d/%d failed (%s); retrying in %ss', attempt, max_retries, exc, delay)
            time.sleep(delay)


def bootstrap() -> None:
    """Run the full first-run bootstrap once per host, with retries while the DB boots.

    Never raises; logs and continues on failure so the app can still serve static
    content and report a degraded health status.
    """
    lock_path = os.getenv('BOOTSTRAP_LOCK', '/tmp/evote_bootstrap.lock')

    @contextmanager
    def _locked():
        lock = open(lock_path, 'w')  # noqa: SIM115 - lock must stay open for the process lifetime
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()

    try:
        with _locked():
            _run()
    except OSError:
        # flock unavailable on this platform: fall back to an unguarded run
        _run()
