import mysql.connector
from mysql.connector import Error
from config import Config

class DatabaseManager:
    def __init__(self, database_name=None):
        self.config = Config.get_db_config(database_name)
        self.conn = None
        self.cursor = None

    def __enter__(self):
        try:
            self.conn = mysql.connector.connect(**self.config)
            self.cursor = self.conn.cursor(buffered=True)
            return self
        except Error as e:
            print(f"Error connecting to database: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()

    def execute_query(self, query, params=None):
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
        return self.cursor.fetchall()

    def fetch_one(self):
        return self.cursor.fetchone()

# Helper for quick connection check or ad-hoc use outside of contexts if absolutely necessary
def get_connection(database_name=None):
    return mysql.connector.connect(**Config.get_db_config(database_name))
