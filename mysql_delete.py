from database import DatabaseManager
from mysql.connector import Error

def delete_column(table, column, db_name=None):
    """
    Deletes a column from a table.
    WARNING: Vulnerable to SQL injection via table/column names if not sanitized.
    """
    try:
        with DatabaseManager(db_name) as db:
            # Note: Table/Column names cannot be parameterized in MySQL connector usually.
            # Ideally, we should validate them against a whitelist or schema.
            # Keeping strictly as-is logic for now but using the new DB manager.
            query = f"ALTER TABLE {table} DROP COLUMN {column}"
            db.execute_query(query)
            print(f"Column {column} deleted successfully from {table}.")
    except Error as e:
        print(f"Error deleting column: {e}")

def delete_row(table, condition, db_name=None):
    """
    Deletes a row based on a condition string.
    WARNING: Highly vulnerable to SQL injection via condition string.
    """
    try:
        with DatabaseManager(db_name) as db:
            query = f"DELETE FROM {table} WHERE {condition}"
            db.execute_query(query)
            print(f"Row deleted successfully from {table}.")
    except Error as e:
        print(f"Error deleting row: {e}")
