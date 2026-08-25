import getpass

import mysql.connector

from config import Config

# SQL statements for creating all database tables

CREATE_DATABASE = """
CREATE DATABASE IF NOT EXISTS {dbname} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
"""

CREATE_REGIONS = """
CREATE TABLE IF NOT EXISTS regions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL
);
"""

CREATE_CONSTITUENCIES = """
CREATE TABLE IF NOT EXISTS constituencies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    region_id INT NOT NULL,
    FOREIGN KEY (region_id) REFERENCES regions(id)
);
"""

CREATE_POLLING_STATIONS = """
CREATE TABLE IF NOT EXISTS polling_stations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    constituency_id INT NOT NULL,
    FOREIGN KEY (constituency_id) REFERENCES constituencies(id)
);
"""

CREATE_PARTIES = """
CREATE TABLE IF NOT EXISTS parties (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    abbreviation VARCHAR(50)
);
"""

CREATE_ELECTIONS = """
CREATE TABLE IF NOT EXISTS elections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    position ENUM('president', 'mp') NOT NULL,
    start_date DATE,
    end_date DATE,
    phase ENUM('nomination', 'campaigning', 'voting', 'results', 'closed') DEFAULT 'nomination',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_CANDIDATES = """
CREATE TABLE IF NOT EXISTS candidates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    party_id INT,
    constituency_id INT,
    election_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (party_id) REFERENCES parties(id),
    FOREIGN KEY (constituency_id) REFERENCES constituencies(id),
    FOREIGN KEY (election_id) REFERENCES elections(id)
);
"""

CREATE_VOTERINFO = """
CREATE TABLE IF NOT EXISTS voterinfo (
    voter_id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    date_of_birth DATE,
    contact VARCHAR(255),
    email VARCHAR(255),
    personal_id VARCHAR(50),
    occupation VARCHAR(100),
    constituency_id INT,
    polling_station_id INT,
    voted BOOLEAN DEFAULT FALSE,
    mp_voted BOOLEAN DEFAULT FALSE,
    president_voted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_voterinfo_personal_id (personal_id),
    FOREIGN KEY (constituency_id) REFERENCES constituencies(id),
    FOREIGN KEY (polling_station_id) REFERENCES polling_stations(id)
);
"""

CREATE_PASS_TABLE = """
CREATE TABLE IF NOT EXISTS pass_table (
    voter_id VARCHAR(255),
    password VARCHAR(255),
    PRIMARY KEY (voter_id),
    FOREIGN KEY (voter_id) REFERENCES voterinfo(voter_id)
);
"""

CREATE_VOTES = """
CREATE TABLE IF NOT EXISTS votes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    candidate_id INT NOT NULL,
    election_id INT NOT NULL,
    polling_station_id INT,
    hmac_hash VARCHAR(255) NOT NULL,
    ballot_paper_id VARCHAR(50) UNIQUE,
    key_version VARCHAR(8) NOT NULL DEFAULT 'k1',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id),
    FOREIGN KEY (election_id) REFERENCES elections(id),
    FOREIGN KEY (polling_station_id) REFERENCES polling_stations(id)
);
"""

CREATE_ADMINS = """
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('super_admin', 'admin', 'viewer') DEFAULT 'admin',
    totp_secret VARCHAR(32) NULL,
    totp_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_AUDIT_LOG = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    action VARCHAR(50) NOT NULL,
    table_name VARCHAR(50),
    record_id VARCHAR(255),
    details TEXT,
    actor VARCHAR(255),
    prev_hash CHAR(64) NOT NULL,
    entry_hash CHAR(64) NOT NULL,
    created_at VARCHAR(35) NOT NULL
);
"""

MIN_ADMIN_PASSWORD_LENGTH = 8

SEED_REGIONS = """
INSERT IGNORE INTO regions (id, name) VALUES
(1, 'Ahafo'), (2, 'Ashanti'), (3, 'Bono'), (4, 'Bono East'),
(5, 'Central'), (6, 'Eastern'), (7, 'Greater Accra'), (8, 'Northern'),
(9, 'North East'), (10, 'Oti'), (11, 'Savannah'), (12, 'Upper East'),
(13, 'Upper West'), (14, 'Volta'), (15, 'Western'), (16, 'Western North');
"""

CREATE_RATE_LIMIT_BUCKETS = """
CREATE TABLE IF NOT EXISTS rate_limit_buckets (
    bucket VARCHAR(255) PRIMARY KEY,
    hits INT NOT NULL DEFAULT 0,
    window_start TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

# Triggers that make the audit log physically append-only: any UPDATE or DELETE
# aborts inside the engine itself rather than relying on application discipline.
AUDIT_IMMUTABILITY_TRIGGERS = [
    """
    CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
    FOR EACH ROW BEGIN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'audit_log is append-only: updates are forbidden';
    END;
    """,
    """
    CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log
    FOR EACH ROW BEGIN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'audit_log is append-only: deletes are forbidden';
    END;
    """,
]

APPLY_TRIGGER_SQL = [
    'DROP TRIGGER IF EXISTS audit_log_no_update',
    'DROP TRIGGER IF EXISTS audit_log_no_delete',
]


def table_exists(cursor, table_name):
    """Check whether a table already exists in the database."""
    cursor.execute('SHOW TABLES LIKE %s', (table_name,))
    return cursor.fetchone() is not None


def setup_database():
    """Create the database, all tables, seed regions, and prompt for the initial admin account."""
    dbname = input(f'Enter database name [{Config.DB_NAME_MAIN}]: ') or Config.DB_NAME_MAIN

    try:
        mydb_connection = mysql.connector.connect(
            host=Config.DB_HOST, user=Config.DB_USER, password=Config.DB_PASSWORD, port=Config.DB_PORT
        )
        cursor = mydb_connection.cursor()
        cursor.execute(CREATE_DATABASE.format(dbname=dbname))
        print(f"Database '{dbname}' checked/created.")
        mydb_connection.close()

        mydb = mysql.connector.connect(
            host=Config.DB_HOST, user=Config.DB_USER, password=Config.DB_PASSWORD, port=Config.DB_PORT, database=dbname
        )
        cursor = mydb.cursor()

        cursor.execute(CREATE_REGIONS)
        cursor.execute(SEED_REGIONS)
        print('regions table created and seeded.')

        cursor.execute(CREATE_CONSTITUENCIES)
        print('constituencies table created.')

        cursor.execute(CREATE_POLLING_STATIONS)
        print('polling_stations table created.')

        cursor.execute(CREATE_PARTIES)
        print('parties table created.')

        cursor.execute(CREATE_ELECTIONS)
        print('elections table created.')

        cursor.execute(CREATE_CANDIDATES)
        print('candidates table created.')

        cursor.execute(CREATE_VOTERINFO)
        print('voterinfo table created.')

        cursor.execute(CREATE_PASS_TABLE)
        print('pass_table created.')

        cursor.execute(CREATE_VOTES)
        print('votes table created.')

        cursor.execute(CREATE_ADMINS)
        print('admins table created.')

        cursor.execute('SELECT COUNT(*) FROM admins')
        if cursor.fetchone()[0] == 0:
            import bcrypt

            print('\n--- First-time setup: Create admin account ---')
            admin_user = input('Admin username [admin]: ') or 'admin'
            admin_pass = getpass.getpass('Admin password: ')
            confirm_pass = getpass.getpass('Confirm password: ')
            while admin_pass != confirm_pass or len(admin_pass) < MIN_ADMIN_PASSWORD_LENGTH:
                if admin_pass != confirm_pass:
                    print('Passwords do not match.')
                else:
                    print('Password must be at least 8 characters.')
                admin_pass = getpass.getpass('Admin password: ')
                confirm_pass = getpass.getpass('Confirm password: ')
            hashed = bcrypt.hashpw(admin_pass.encode('utf-8'), bcrypt.gensalt())
            cursor.execute(
                "INSERT INTO admins(username, password_hash, role) VALUES (%s, %s, 'super_admin')",
                (admin_user, hashed.decode('utf-8')),
            )
            print(f"Admin '{admin_user}' created.")

        cursor.execute(CREATE_AUDIT_LOG)
        print('audit_log table created.')

        for drop_sql, trigger_ddl in zip(APPLY_TRIGGER_SQL, AUDIT_IMMUTABILITY_TRIGGERS):
            cursor.execute(drop_sql)
            cursor.execute(trigger_ddl)
        print('audit_log immutability triggers installed.')

        mydb.commit()
        cursor.close()
        mydb.close()
        print('All tables created successfully!')

    except mysql.connector.Error as err:
        print(f'Error creating database/tables: {err}')


if __name__ == '__main__':
    setup_database()
