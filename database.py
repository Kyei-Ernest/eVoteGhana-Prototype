import mysql.connector
from mysql.connector import Error
from config import Config


class DatabaseManager:
    def __init__(self, database_name: str | None = None):
        self.config = Config.get_db_config(database_name)
        self.conn: mysql.connector.MySQLConnection | None = None
        self.cursor: mysql.connector.cursor.MySQLCursor | None = None

    def __enter__(self) -> 'DatabaseManager':
        try:
            self.conn = mysql.connector.connect(**self.config)
            self.cursor = self.conn.cursor(buffered=True)
            return self
        except Error as e:
            print(f"Error connecting to database: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.cursor:
            self.cursor.close()
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()

    def execute_query(self, query: str, params: tuple | None = None) -> mysql.connector.cursor.MySQLCursor:
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            return self.cursor
        except Error as e:
            print(f"Error executing query: {e}")
            raise

    def fetch_all(self) -> list[tuple]:
        return self.cursor.fetchall()

    def fetch_one(self) -> tuple | None:
        return self.cursor.fetchone()


def get_connection(database_name: str | None = None) -> mysql.connector.MySQLConnection:
    return mysql.connector.connect(**Config.get_db_config(database_name))
