"""Database access with optional connection pooling.

Every consumer uses the ``DatabaseManager`` context manager, which commits on
success and rolls back on exception. When ``DB_POOL_SIZE`` is greater than zero
connections are borrowed from a process local ``MySQLConnectionPool`` instead of
being opened per operation; closing a pooled connection returns it to the pool.
Pools are keyed by database name because the identity lookup helpers target a
separate database.
"""

import os

import mysql.connector
from mysql.connector import Error, pooling

from config import Config

_POOL_CACHE: dict[str, pooling.MySQLConnectionPool] = {}


def _get_pool(database_name: str | None) -> pooling.MySQLConnectionPool | None:
    try:
        size = int(os.getenv('DB_POOL_SIZE', '0'))
    except ValueError:
        size = 0
    if size <= 0:
        return None
    key = database_name or Config.DB_NAME_MAIN
    if key not in _POOL_CACHE:
        _POOL_CACHE[key] = pooling.MySQLConnectionPool(
            pool_name=f'evote_{key}',
            pool_size=size,
            pool_reset_session=True,
            **Config.get_db_config(key),
        )
    return _POOL_CACHE[key]


class DatabaseManager:
    def __init__(self, database_name: str | None = None):
        self.config = Config.get_db_config(database_name)
        self.conn: mysql.connector.MySQLConnection | None = None
        self.cursor: mysql.connector.cursor.MySQLCursor | None = None

    def __enter__(self) -> 'DatabaseManager':
        try:
            pool = _get_pool(self.config.get('database'))
            self.conn = pool.get_connection() if pool else mysql.connector.connect(**self.config)
            self.cursor = self.conn.cursor(buffered=True)
            return self
        except Error as e:
            print(f'Error connecting to database: {e}')
            raise

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.cursor:
            self.cursor.close()
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            # Closing a pooled connection hands it back to the pool.
            self.conn.close()

    def execute_query(self, query: str, params: tuple | None = None) -> mysql.connector.cursor.MySQLCursor:
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            return self.cursor
        except Error as e:
            print(f'Error executing query: {e}')
            raise

    def fetch_all(self) -> list[tuple]:
        return self.cursor.fetchall()

    def fetch_one(self) -> tuple | None:
        return self.cursor.fetchone()


def get_connection(database_name: str | None = None) -> mysql.connector.MySQLConnection:
    return mysql.connector.connect(**Config.get_db_config(database_name))
