from database import DatabaseManager

VALID_TABLES = {'voterinfo', 'pass_table', 'candidates', 'parties', 'elections',
                'constituencies', 'polling_stations', 'regions', 'votes', 'audit_log', 'admins'}


def _validate_table(table):
    """Raise ValueError if the table name is not in the allowed set."""
    if table not in VALID_TABLES:
        raise ValueError(f"Invalid table: {table}")
    return table


def delete_row(table, column, value, db_name=None):
    """Delete rows from a validated table where the column matches the given value."""
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
