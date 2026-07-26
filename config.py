import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'admin123')
    DB_NAME_MAIN = os.getenv('DB_NAME_MAIN', 'mydb')
    DB_NAME_IDENTITY = os.getenv('DB_NAME_IDENTITY', 'gg')
    DB_PORT = int(os.getenv('DB_PORT', 3306))

    @staticmethod
    def get_db_config(database_name=None):
        """Returns a dictionary for mysql.connector"""
        return {
            'host': Config.DB_HOST,
            'user': Config.DB_USER,
            'password': Config.DB_PASSWORD,
            'database': database_name if database_name else Config.DB_NAME_MAIN,
            'port': Config.DB_PORT
        }
