import mysql.connector
from config import Config
import bcrypt


def migrate():
    """Migrate legacy schema (presidents, members_of_parliament tables) to the new unified schema."""
    dbname = input(f"Database to migrate [{Config.DB_NAME_MAIN}]: ") or Config.DB_NAME_MAIN

    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST, user=Config.DB_USER,
            password=Config.DB_PASSWORD, port=Config.DB_PORT,
            database=dbname
        )
        cursor = conn.cursor()

        cursor.execute("SHOW TABLES LIKE 'presidents'")
        has_old_schema = cursor.fetchone() is not None

        if not has_old_schema:
            print("No old schema detected (presidents table not found). Nothing to migrate.")
            conn.close()
            return

        print("Old schema detected. Starting migration...")

        import schema as new_schema
        cursor.execute(new_schema.CREATE_REGIONS)
        cursor.execute(new_schema.SEED_REGIONS)

        cursor.execute("SHOW TABLES LIKE 'members_of_parliament'")
        has_mop = cursor.fetchone() is not None

        if has_mop:
            cursor.execute("SELECT DISTINCT constituency FROM members_of_parliament")
            old_constituencies = cursor.fetchall()

            cursor.execute("SELECT id, name FROM regions LIMIT 1")
            default_region = cursor.fetchone()
            region_id = default_region[0] if default_region else 1

            for (const_name,) in old_constituencies:
                if const_name:
                    cursor.execute("INSERT IGNORE INTO constituencies(name, region_id) VALUES (%s, %s)",
                                   (const_name.strip(), region_id))

            cursor.execute("SELECT column_name FROM information_schema.columns "
                           "WHERE table_name = 'members_of_parliament' AND table_schema = %s "
                           "AND column_name NOT IN ('id', 'constituency')", (dbname,))
            party_columns = [row[0] for row in cursor.fetchall()]

            pres_count = 0
            mp_count = 0
            for party_col in party_columns:
                # Each column in members_of_parliament (besides id/constituency) represents a party
                party_name = party_col.replace('_', ' ').title().strip()
                if party_name.lower() == 'none':
                    continue
                cursor.execute("INSERT IGNORE INTO parties(name) VALUES (%s)", (party_name,))
                cursor.execute("SELECT id FROM parties WHERE name = %s", (party_name,))
                party_row = cursor.fetchone()
                party_id = party_row[0] if party_row else None

                # Migrate presidential candidates from the presidents table
                cursor.execute("SELECT presidential_candidate_name FROM presidents WHERE political_party = %s",
                               (party_name,))
                pres = cursor.fetchone()
                if pres:
                    cursor.execute("INSERT INTO elections(title, position, phase) VALUES (%s, 'president', 'closed')",
                                   (f"{party_name} Presidential Election",))
                    eid = cursor.lastrowid
                    cursor.execute("INSERT INTO candidates(name, party_id, election_id) VALUES (%s, %s, %s)",
                                   (pres[0], party_id, eid))
                    pres_count += 1

                # Migrate MP candidates from members_of_parliament column values
                cursor.execute("SELECT * FROM members_of_parliament")
                mop_rows = cursor.fetchall()
                col_index = party_columns.index(party_col) + 2

                for row in mop_rows:
                    if col_index < len(row) and row[col_index]:
                        const_name = row[1] if len(row) > 1 else None
                        if const_name:
                            cursor.execute("SELECT id FROM constituencies WHERE name = %s", (const_name.strip(),))
                            const_row = cursor.fetchone()
                            const_id = const_row[0] if const_row else None

                            cursor.execute("INSERT INTO elections(title, position, phase) VALUES (%s, 'mp', 'closed')",
                                           (f"{const_name} MP Election",))
                            eid = cursor.lastrowid
                            cursor.execute("""INSERT INTO candidates(name, party_id, constituency_id, election_id)
                                              VALUES (%s, %s, %s, %s)""", (row[col_index], party_id, const_id, eid))
                            mp_count += 1

        cursor.execute(new_schema.CREATE_CANDIDATES)
        cursor.execute(new_schema.CREATE_ELECTIONS)
        cursor.execute(new_schema.CREATE_VOTES)
        cursor.execute(new_schema.CREATE_AUDIT_LOG)

        cursor.execute("SHOW COLUMNS FROM voterinfo LIKE 'constituency'")
        has_constituency_col = cursor.fetchone() is not None

        if has_constituency_col:
            cursor.execute("ALTER TABLE voterinfo ADD COLUMN IF NOT EXISTS constituency_id INT, "
                           "ADD COLUMN IF NOT EXISTS polling_station_id INT")

            cursor.execute("SELECT DISTINCT constituency FROM voterinfo WHERE constituency IS NOT NULL")
            for (const_name,) in cursor.fetchall():
                cursor.execute("SELECT id FROM constituencies WHERE name = %s", (const_name.strip(),))
                const_row = cursor.fetchone()
                if const_row:
                    cid = const_row[0]
                    cursor.execute("UPDATE voterinfo SET constituency_id = %s WHERE constituency = %s",
                                   (cid, const_name))

        cursor.execute(new_schema.CREATE_VOTERINFO)

        cursor.execute("SELECT id, username FROM admins LIMIT 1")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO admins(username, password_hash, role) VALUES (%s, %s, 'super_admin')",
                           ('admin', bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')))
            print("Default admin account created: admin / admin123")

        conn.commit()
        print(f"\nMigration complete! Migrated {pres_count} presidential and {mp_count} MP candidates.")
        print("Note: Old tables (presidents, members_of_parliament) were kept for safety.")
        print("You can drop them manually after verifying the migration.")

        cursor.close()
        conn.close()

    except mysql.connector.Error as err:
        print(f"Migration error: {err}")


if __name__ == "__main__":
    migrate()
