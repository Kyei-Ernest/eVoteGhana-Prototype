import os
import secrets
from dotenv import load_dotenv

load_dotenv()


class Config:
    DB_HOST: str = os.getenv('DB_HOST', '127.0.0.1')
    DB_USER: str = os.getenv('DB_USER', 'root')
    DB_PASSWORD: str = os.getenv('DB_PASSWORD', '')
    DB_NAME_MAIN: str = os.getenv('DB_NAME_MAIN', 'mydb')
    DB_NAME_IDENTITY: str = os.getenv('DB_NAME_IDENTITY', 'gg')
    DB_PORT: int = int(os.getenv('DB_PORT', 3306))

    @staticmethod
    def get_db_config(database_name: str | None = None) -> dict:
        return {
            'host': Config.DB_HOST,
            'user': Config.DB_USER,
            'password': Config.DB_PASSWORD,
            'database': database_name if database_name else Config.DB_NAME_MAIN,
            'port': Config.DB_PORT
        }

    @staticmethod
    def get_hmac_key() -> str:
        key = os.getenv('HMAC_SECRET_KEY', '')
        if not key or key == 'change-this-to-a-secure-random-key-in-production':
            print("WARNING: HMAC_SECRET_KEY is insecure. Set a strong key in production.")
        return key or secrets.token_hex(32)
