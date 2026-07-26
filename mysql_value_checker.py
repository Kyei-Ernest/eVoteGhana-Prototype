from database import DatabaseManager
from mysql.connector import Error

def check_value_exists(table, column, user_input, db_name=None):
    """
    Checks if a value exists in a particular column in a database table.
    """
    try:
        with DatabaseManager(db_name) as db:
            query = f"SELECT COUNT(*) FROM {table} WHERE {column} = %s"
            db.execute_query(query, (user_input,))
            result = db.fetch_one()[0]
            return result > 0
    except Error as e:
        print(f"Error checking value existence: {e}")
        return False

def check_column_exists(table_name, column_name, db_name=None):
    """
    Checks if a column exists in a database table.
    """
    try:
        with DatabaseManager(db_name) as db:
            query = f"SHOW COLUMNS FROM {table_name};"
            db.execute_query(query)
            columns = db.fetch_all()
            return any(column[0] == column_name for column in columns)
    except Error as e:
        print(f"Error checking column existence: {e}")
        return False
