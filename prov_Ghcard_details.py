import random
import string
from datetime import datetime

import mysql.connector
from mysql.connector import errorcode

from config import Config

cnx = mysql.connector.connect(
    host=Config.DB_HOST, user=Config.DB_USER, password=Config.DB_PASSWORD, port=Config.DB_PORT
)
cursor = cnx.cursor()


def create_database(cursor_, db_name):
    """Create a new MySQL database; return True if created, False if it already exists."""
    try:
        cursor_.execute(f'CREATE DATABASE {db_name}')
        print(f"Database '{db_name}' created successfully.")
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_DB_CREATE_EXISTS:
            print(f"Database '{db_name}' already exists.")
            return False
        else:
            print(err.msg)
            return False
    return True


def create_table(cursor__, db_name):
    """Create the ECOWAS_Identity table with an auto-calculated expiry date (10 years from insurance)."""
    try:
        cursor__.execute(f'USE {db_name}')
        cursor__.execute("""
            CREATE TABLE ECOWAS_Identity (
                personal_id VARCHAR(255) PRIMARY KEY,
                surname VARCHAR(255),
                firstname VARCHAR(255),
                other_names VARCHAR(255),
                date_of_birth DATE,
                nationality VARCHAR(255),
                place_of_insurance VARCHAR(255),
                date_of_insurance DATE,
                date_of_expiry DATE GENERATED ALWAYS AS (DATE_ADD(date_of_insurance, INTERVAL 10 YEAR)) STORED
            )
        """)
        print(f"Table ECOWAS Identity created successfully in database '{db_name}'.")
    except mysql.connector.Error as err:
        print(err.msg)


def generate_random_personal_id():
    """Generate a random Ghana-card-style personal ID with GHA- prefix."""
    random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    return f'GHA-{random_chars}'


def generate_random_name():
    """Generate a random 7-character uppercase string to simulate a name."""
    return ''.join(random.choices(string.ascii_uppercase, k=7))


def insert_data(cursor___, db_name, iterations):
    """Insert a specified number of randomly generated identity records into the ECOWAS_Identity table."""
    cities_in_ghana = [
        'Accra',
        'Kumasi',
        'Tamale',
        'Takoradi',
        'Cape Coast',
        'Koforidua',
        'Sunyani',
        'Ho',
        'Bolgatanga',
        'Wa',
    ]
    cursor___.execute(f'USE {db_name}')

    for _ in range(iterations):
        personal_id = generate_random_personal_id()
        surname = generate_random_name()
        firstname = generate_random_name()
        other_names = generate_random_name()
        date_of_birth = '2005-03-11'
        nationality = 'GHANAIAN'
        place_of_insurance = random.choice(cities_in_ghana)
        date_of_insurance = datetime.now().date()

        try:
            cursor___.execute(
                """
                INSERT INTO ECOWAS_Identity
                    (personal_id, surname, firstname, other_names, date_of_birth,
                     nationality, place_of_insurance, date_of_insurance)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    personal_id,
                    surname,
                    firstname,
                    other_names,
                    date_of_birth,
                    nationality,
                    place_of_insurance,
                    date_of_insurance,
                ),
            )
            cnx.commit()
            print(f'Inserted data for personal_id: {personal_id}')
        except mysql.connector.Error as err:
            print(f'Error: {err}')


def main():
    """Prompt user for database name and record count, then create and populate the ECOWAS_Identity table."""
    while True:
        db_name = input('Enter the name of the database to create: ')
        if create_database(cursor, db_name):
            create_table(cursor, db_name)
            break
        else:
            print('Please enter a different database name.')

    iterations = int(input('Enter the number of data sets to create: '))
    insert_data(cursor, db_name, iterations)


if __name__ == '__main__':
    main()

cursor.close()
cnx.close()
