from database import DatabaseManager

VALID_TABLES: set[str] = {'voterinfo', 'pass_table', 'candidates', 'parties', 'elections',
                          'constituencies', 'polling_stations', 'regions', 'votes', 'audit_log', 'admins'}
VALID_COLUMNS_CACHE: dict[str, set[str]] = {}


def _get_valid_columns(table: str) -> set[str]:
    if table not in VALID_COLUMNS_CACHE:
        try:
            with DatabaseManager() as db:
                db.execute_query(f"SHOW COLUMNS FROM {table}")
                VALID_COLUMNS_CACHE[table] = {row[0] for row in db.fetch_all()}
        except Exception:
            return set()
    return VALID_COLUMNS_CACHE[table]


def _validate_table(table: str) -> str:
    if table not in VALID_TABLES:
        raise ValueError(f"Invalid table: {table}")
    return table


def _validate_column(table: str, column: str) -> str:
    valid = _get_valid_columns(table)
    if column not in valid:
        raise ValueError(f"Invalid column '{column}' for table '{table}'")
    return column


def check_value_exists(table: str, column: str, user_input: str, db_name: str | None = None) -> bool:
    try:
        _validate_table(table)
        _validate_column(table, column)
        with DatabaseManager(db_name) as db:
            query = f"SELECT COUNT(*) FROM {table} WHERE {column} = %s"
            db.execute_query(query, (user_input,))
            return db.fetch_one()[0] > 0
    except (ValueError, Exception) as e:
        print(f"Error checking value: {e}")
        return False


def check_column_exists(table_name: str, column_name: str, db_name: str | None = None) -> bool:
    try:
        _validate_table(table_name)
        with DatabaseManager(db_name) as db:
            db.execute_query(f"SHOW COLUMNS FROM {table_name}")
            return any(row[0] == column_name for row in db.fetch_all())
    except Exception as e:
        print(f"Error checking column: {e}")
        return False
