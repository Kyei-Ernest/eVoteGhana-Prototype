import mysql.connector
from config import Config

# MySQL statements for creating tables
create_voterinfo_table = """
CREATE TABLE IF NOT EXISTS voterinfo (
  voter_id VARCHAR(255) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  date_of_birth DATE,
  contact VARCHAR(255),
  email VARCHAR(255),
  personal_id VARCHAR(50),
  occupation VARCHAR(100),
  constituency VARCHAR(100),
  voted BOOLEAN DEFAULT FALSE,
  president_vote VARCHAR(255),
  mp_vote VARCHAR(255)
);
"""

create_president_table = """
CREATE TABLE IF NOT EXISTS presidents(
  id INT AUTO_INCREMENT PRIMARY KEY,
  political_party VARCHAR(100),
  presidential_candidate_name VARCHAR(255) NOT NULL,
  number_of_votes INT DEFAULT 0,
  vote_percentage VARCHAR(255)
);
"""

create_mpvotesinfo_table = """
CREATE TABLE IF NOT EXISTS members_of_parliament (
  id INT AUTO_INCREMENT PRIMARY KEY,
  constituency VARCHAR(100)
);
"""

create_pass_table = '''
CREATE TABLE IF NOT EXISTS pass_table (
    voter_id VARCHAR(255),
    password VARCHAR(255),
    PRIMARY KEY (voter_id),
    FOREIGN KEY (voter_id) REFERENCES voterinfo(voter_id)
);
'''

def setup_database():
    dbname = input(f"Enter database name [{Config.DB_NAME_MAIN}]: ") or Config.DB_NAME_MAIN  

    try:
        # Connect to MySQL server (no database selected yet)
        mydb_connection = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            port=Config.DB_PORT
        )
        cursor = mydb_connection.cursor()
        
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {dbname} CHARACTER SET utf8 COLLATE utf8_general_ci;")
        print(f"Database '{dbname}' checked/created.")
        
        mydb_connection.close()

        # Now connect to the database
        mydb = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            port=Config.DB_PORT,
            database=dbname
        )
        cursor = mydb.cursor()

        # Execute table creation statements
        cursor.execute(create_voterinfo_table)
        print("voterinfo table created.")
        cursor.execute(create_president_table)
        print("presidents table created.")
        cursor.execute(create_mpvotesinfo_table)
        print("members_of_parliament table created.")
        cursor.execute(create_pass_table)
        print("pass_table table created.")

        mydb.commit()
        cursor.close()
        mydb.close()

        print("All tables created successfully!")

    except mysql.connector.Error as err:
        print("Error creating database/tables:", err)

if __name__ == "__main__":
    setup_database()
