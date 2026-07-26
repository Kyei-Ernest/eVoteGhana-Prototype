import random
import string
import getpass
from datetime import datetime
import bcrypt
from age_calc import age
import mysql_value_checker as vc
import mysql_delete as de
from database import DatabaseManager
from audit_log import log_action


class RegisterVoter:
    def __init__(self, voter_id, name, contact, email, date_of_birth, personal_id, occupation,
                 constituency_id, polling_station_id, password, conf_pass):
        self.id = voter_id
        self.name = name
        self.date_of_birth = date_of_birth
        self.contact = contact
        self.email = email
        self.personal_id = personal_id
        self.occupation = occupation
        self.constituency_id = constituency_id
        self.polling_station_id = polling_station_id
        self.password = password
        self.conf_pass = conf_pass
        self.legal_age = 0

    def calculate_age(self):
        try:
            day, month, year = map(int, self.date_of_birth.split("/"))
            then = datetime(year=year, month=month, day=day)
            self.legal_age = age(then)
            return self.legal_age
        except ValueError as e:
            print(f"Error calculating age: {e}")
            return -1

    def full_info(self):
        try:
            hashed_password = RegisterVoter.create_hashed_password(self.password)
            python_date = datetime.strptime(self.date_of_birth, '%d/%m/%Y')
            mysql_date = python_date.strftime('%Y-%m-%d')

            with DatabaseManager() as db:
                sql = """INSERT INTO voterinfo(voter_id, name, contact, email, date_of_birth, personal_id,
                         occupation, constituency_id, polling_station_id, voted)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                db.execute_query(sql, (self.id, self.name, self.contact, self.email, mysql_date,
                                       self.personal_id, self.occupation, self.constituency_id,
                                       self.polling_station_id, 0))

                sql_1 = "INSERT INTO pass_table(voter_id, password) VALUES (%s, %s)"
                db.execute_query(sql_1, (self.id, hashed_password))

            log_action('voter_registered', 'voterinfo', self.id,
                       f"Name: {self.name}, Constituency: {self.constituency_id}")
            print(f"Voter {self.name} registered successfully.")
            return True
        except ValueError as e:
            print(f"Error parsing date: {e}")
            return False
        except Exception as err:
            print(f"Error inserting into database: {err}")
            return False

    @staticmethod
    def create_hashed_password(password):
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt)

    def verification(self):
        try:
            self.calculate_age()

            id_exists = vc.check_value_exists('voterinfo', 'voter_id', self.id)
            const_exists = vc.check_value_exists('constituencies', 'id', self.constituency_id)
            ps_exists = vc.check_value_exists('polling_stations', 'id', self.polling_station_id)

            if id_exists:
                print("Sorry, this ID already exists for another voter")
                id_list = random.choices(string.ascii_uppercase + string.digits, k=8)
                self.id = "".join(id_list)
                return self.verification()
            elif self.legal_age < 18:
                print("You are not eligible for voting")
                return False
            elif not self.name or isinstance(self.name, int):
                print('Must enter a valid name')
                self.name = input("Name: ")
                return self.verification()
            elif not self.date_of_birth:
                print('Date of birth required')
                self.date_of_birth = input("Date of birth (DD/MM/YYYY): ")
                return self.verification()
            elif not self.occupation:
                print('Occupation required')
                self.occupation = input("Occupation: ")
                return self.verification()
            elif not self.contact or len(self.contact) != 10:
                print("Contact must be exactly 10 digits")
                self.contact = input("Contact: ")
                return self.verification()
            elif not const_exists:
                print('Constituency does not exist')
                return False
            elif not ps_exists:
                print('Polling station does not exist')
                return False
            elif self.password != self.conf_pass:
                print('The passwords you entered do not match')
                self.password = getpass.getpass('Password: ')
                self.conf_pass = getpass.getpass('Confirm Password: ')
                return self.verification()
            elif len(self.password) < 10 or len(self.conf_pass) < 10:
                print('Password must contain more than 10 characters.')
                self.password = getpass.getpass('Password: ')
                self.conf_pass = getpass.getpass('Confirm Password: ')
                return self.verification()
            else:
                return self.full_info()

        except Exception as err:
            print(f"Database error: {err}")
            return False


def list_polling_stations():
    try:
        with DatabaseManager() as db:
            db.execute_query("""SELECT ps.id, ps.name, ps.code, c.name
                                FROM polling_stations ps
                                JOIN constituencies c ON ps.constituency_id = c.id
                                ORDER BY c.name, ps.name""")
            stations = db.fetch_all()
            if not stations:
                print("No polling stations found.")
            else:
                print("\n--- Polling Stations ---")
                for s in stations:
                    print(f"{s[0]}: {s[1]} ({s[2]}) - {s[3]}")
            return stations
    except Exception as e:
        print(f"Error: {e}")
        return []


def list_constituencies():
    try:
        with DatabaseManager() as db:
            db.execute_query("""SELECT c.id, c.name, r.name FROM constituencies c
                                JOIN regions r ON c.region_id = r.id ORDER BY c.name""")
            results = db.fetch_all()
            if not results:
                print("No constituencies found.")
            else:
                print("\n--- Constituencies ---")
                for r in results:
                    print(f"{r[0]}: {r[1]} ({r[2]})")
            return results
    except Exception as e:
        print(f"Error: {e}")
        return []


def list_regions():
    try:
        with DatabaseManager() as db:
            db.execute_query("SELECT id, name FROM regions ORDER BY name")
            regions = db.fetch_all()
            for r in regions:
                print(f"{r[0]}: {r[1]}")
            return regions
    except Exception as e:
        print(f"Error: {e}")
        return []


def list_parties():
    try:
        with DatabaseManager() as db:
            db.execute_query("SELECT id, name, abbreviation FROM parties ORDER BY name")
            parties = db.fetch_all()
            if not parties:
                print("No parties registered.")
            else:
                print("\n--- Political Parties ---")
                for p in parties:
                    print(f"{p[0]}: {p[1]} ({p[2] or 'N/A'})")
            return parties
    except Exception as e:
        print(f"Error: {e}")
        return []


def list_elections():
    try:
        with DatabaseManager() as db:
            db.execute_query("SELECT id, title, position, phase FROM elections ORDER BY id")
            elections = db.fetch_all()
            if not elections:
                print("No elections found.")
            else:
                print("\n--- Elections ---")
                for e in elections:
                    print(f"{e[0]}: {e[1]} ({e[2]}) - Phase: {e[3]}")
            return elections
    except Exception as e:
        print(f"Error: {e}")
        return []


def setup_election():
    title = input("Election title: ")
    position = input("Position (president/mp): ").strip().lower()
    if position not in ('president', 'mp'):
        print("Invalid position.")
        return
    try:
        with DatabaseManager() as db:
            db.execute_query("INSERT INTO elections(title, position, phase) VALUES (%s, %s, 'nomination')",
                             (title, position))
            eid = db.cursor.lastrowid
            log_action('election_created', 'elections', eid, f"{title} ({position})")
            print(f"Election '{title}' created with ID {eid}.")
    except Exception as e:
        print(f"Error creating election: {e}")


def transition_election():
    elections = list_elections()
    if not elections:
        return
    try:
        eid = int(input("Enter election ID to transition: "))
        from election import PHASES, transition_phase
        print("Available phases:", ", ".join(PHASES))
        new_phase = input("Enter new phase: ").strip().lower()
        if new_phase in PHASES:
            transition_phase(eid, new_phase)
        else:
            print("Invalid phase.")
    except ValueError:
        print("Invalid ID.")


def add_party():
    name = input("Party name: ")
    abbreviation = input("Abbreviation (e.g., NPP, NDC): ")
    try:
        with DatabaseManager() as db:
            db.execute_query("INSERT INTO parties(name, abbreviation) VALUES (%s, %s)", (name, abbreviation))
            pid = db.cursor.lastrowid
            log_action('party_added', 'parties', pid, name)
            print(f"Party '{name}' added.")
    except Exception as e:
        print(f"Error adding party: {e}")


def add_region():
    regions = list_regions()
    if regions:
        print("Regions already exist.")
        return
    ghana_regions = [
        'Ahafo', 'Ashanti', 'Bono', 'Bono East', 'Central', 'Eastern',
        'Greater Accra', 'Northern', 'North East', 'Oti', 'Savannah',
        'Upper East', 'Upper West', 'Volta', 'Western', 'Western North'
    ]
    try:
        with DatabaseManager() as db:
            for name in ghana_regions:
                db.execute_query("INSERT IGNORE INTO regions(name) VALUES (%s)", (name,))
            print("All 16 regions of Ghana added.")
    except Exception as e:
        print(f"Error adding regions: {e}")


def add_constituency():
    list_regions()
    try:
        region_id = int(input("Enter region ID: "))
        name = input("Constituency name: ")
        with DatabaseManager() as db:
            db.execute_query("INSERT INTO constituencies(name, region_id) VALUES (%s, %s)", (name, region_id))
            cid = db.cursor.lastrowid
            log_action('constituency_added', 'constituencies', cid, name)
            print(f"Constituency '{name}' added.")
    except Exception as e:
        print(f"Error adding constituency: {e}")


def add_polling_station():
    list_constituencies()
    try:
        constituency_id = int(input("Enter constituency ID: "))
        name = input("Polling station name: ")
        code = input("Polling station code: ")
        with DatabaseManager() as db:
            db.execute_query("""INSERT INTO polling_stations(name, code, constituency_id)
                                VALUES (%s, %s, %s)""", (name, code, constituency_id))
            psid = db.cursor.lastrowid
            log_action('polling_station_added', 'polling_stations', psid, f"{name} ({code})")
            print(f"Polling station '{name}' added.")
    except Exception as e:
        print(f"Error adding polling station: {e}")


def add_presidential_candidate():
    list_elections()
    list_parties()
    try:
        election_id = int(input("Enter election ID: "))
        name = input("Candidate name: ")
        party_id = int(input("Party ID: "))
        with DatabaseManager() as db:
            db.execute_query("""INSERT INTO candidates(name, party_id, election_id)
                                VALUES (%s, %s, %s)""", (name, party_id, election_id))
            cid = db.cursor.lastrowid
            log_action('candidate_added', 'candidates', cid, f"President: {name}")
            print(f"Presidential candidate '{name}' added.")
    except Exception as e:
        print(f"Error adding candidate: {e}")


def add_mp_candidate():
    list_elections()
    list_parties()
    list_constituencies()
    try:
        election_id = int(input("Enter election ID: "))
        name = input("Candidate name: ")
        party_id = int(input("Party ID (0 for independent): "))
        constituency_id = int(input("Constituency ID: "))
        with DatabaseManager() as db:
            if party_id == 0:
                db.execute_query("""INSERT INTO candidates(name, constituency_id, election_id)
                                    VALUES (%s, %s, %s)""", (name, constituency_id, election_id))
            else:
                db.execute_query("""INSERT INTO candidates(name, party_id, constituency_id, election_id)
                                    VALUES (%s, %s, %s, %s)""", (name, party_id, constituency_id, election_id))
            cid = db.cursor.lastrowid
            log_action('candidate_added', 'candidates', cid, f"MP: {name}")
            print(f"MP candidate '{name}' added.")
    except Exception as e:
        print(f"Error adding MP candidate: {e}")


def start_other_registration():
    while True:
        print("""
1. Manage Elections (create/transition)
2. Add regions (16 Ghana regions)
3. Add constituency
4. Add polling station
5. Add political party
6. Add presidential candidate
7. Add MP candidate
8. List all (constituencies, stations, parties, elections)
9. Exit
        """)
        choice = input("Enter choice: ")

        if choice == '1':
            print("\n1. Create election\n2. Transition election phase")
            sub = input("Choice: ")
            if sub == '1':
                setup_election()
            elif sub == '2':
                transition_election()
        elif choice == '2':
            add_region()
        elif choice == '3':
            add_constituency()
        elif choice == '4':
            add_polling_station()
        elif choice == '5':
            add_party()
        elif choice == '6':
            add_presidential_candidate()
        elif choice == '7':
            add_mp_candidate()
        elif choice == '8':
            list_regions()
            list_constituencies()
            list_polling_stations()
            list_parties()
            list_elections()
        elif choice == '9':
            break


def start_voter_registration_process():
    while True:
        choice = input("""
1. Register
2. Exit
Enter your choice: """)

        if choice == "1":
            id_list = random.choices(string.ascii_uppercase + string.digits, k=8)
            ID = "".join(id_list)
            name = input('Full Name: ')
            dob = input('Date of birth (DD/MM/YYYY): ')
            contact = input('Contact: ')
            email = input('Email: ')
            personal_id = input('Personal ID: ')
            occupation = input('Occupation: ')
            list_constituencies()
            try:
                constituency_id = int(input('Constituency ID: '))
            except ValueError:
                print("Invalid ID.")
                break
            list_polling_stations()
            try:
                polling_station_id = int(input('Polling Station ID: '))
            except ValueError:
                print("Invalid ID.")
                break
            password = getpass.getpass('Password: ')
            confirm = getpass.getpass('Confirm Password: ')

            svrp = RegisterVoter(
                voter_id=ID, name=name, date_of_birth=dob,
                contact=contact, email=email, personal_id=personal_id,
                occupation=occupation, constituency_id=constituency_id,
                polling_station_id=polling_station_id,
                password=password, conf_pass=confirm
            )
            svrp.verification()
            break

        elif choice == "2":
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please enter 1 or 2.")
