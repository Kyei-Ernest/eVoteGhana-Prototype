from database import DatabaseManager

VALID_TABLES = {'voterinfo', 'pass_table', 'candidates', 'parties', 'elections',
                'constituencies', 'polling_stations', 'regions', 'votes', 'audit_log'}


def _validate_table(table):
    if table not in VALID_TABLES:
        raise ValueError(f"Invalid table: {table}")
    return table


def delete_row(table, column, value, db_name=None):
    try:
        _validate_table(table)
        with DatabaseManager(db_name) as db:
            query = f"DELETE FROM {table} WHERE {column} = %s"
            db.execute_query(query, (value,))
            affected = db.cursor.rowcount
            print(f"Deleted {affected} row(s) from {table}.")
            return affected
    except Exception as e:
        print(f"Error deleting row: {e}")
        return 0
