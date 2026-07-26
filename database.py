import mysql.connector
from mysql.connector import Error
from config import Config


class DatabaseManager:
    """Context manager for MySQL database connections with automatic commit/rollback."""
    def __init__(self, database_name=None):
        self.config = Config.get_db_config(database_name)
        self.conn = None
        self.cursor = None

    def __enter__(self):
        """Open a database connection and return the manager instance."""
        try:
            self.conn = mysql.connector.connect(**self.config)
            self.cursor = self.conn.cursor(buffered=True)
            return self
        except Error as e:
            print(f"Error connecting to database: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close the cursor and connection, committing on success or rolling back on error."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()

    def execute_query(self, query, params=None):
        """Execute a SQL query with optional parameters and return the cursor."""
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            return self.cursor
        except Error as e:
            print(f"Error executing query: {e}")
            raise

    def fetch_all(self):
        """Fetch all remaining rows from the last executed query."""
        return self.cursor.fetchall()

    def fetch_one(self):
        """Fetch the next row from the last executed query."""
        return self.cursor.fetchone()


def get_connection(database_name=None):
    """Create and return a raw MySQL connection outside the context manager."""
    return mysql.connector.connect(**Config.get_db_config(database_name))
