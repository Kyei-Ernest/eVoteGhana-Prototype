import ballot_creation as bc
import bcrypt
import getpass
from datetime import datetime
from database import DatabaseManager
from hmac_utils import compute_vote_hmac, generate_ballot_paper_id
from election import get_current_phase, require_phase
from rate_limiter import voter_auth_limiter


def verify_password(stored_password, provided_password):
    if isinstance(stored_password, str):
        stored_password = stored_password.encode('utf-8')
    return bcrypt.checkpw(provided_password.encode('utf-8'), stored_password)


def vote_mp():
    voters_id = input("Enter voter ID: ")

    if not voter_auth_limiter.is_allowed(voters_id):
        print("Too many attempts. Try again in 5 minutes.")
        return

    try:
        with DatabaseManager() as db:
            mp_election_id = bc.get_mp_election_id()
            if not mp_election_id:
                print("No active MP election.")
                return

            if not require_phase(mp_election_id, 'voting'):
                return

            votesql = "SELECT voted, polling_station_id, personal_id FROM voterinfo WHERE voter_id = %s"
            db.execute_query(votesql, (voters_id,))
            result = db.fetch_one()

            if not result:
                print("Voter ID not found.")
                return

            voted_already, polling_station_id, stored_personal_id = result

            if not voted_already:
                personal_id_verify = getpass.getpass('Enter Ghana Card (Personal ID) for verification: ')
                if personal_id_verify.strip().upper() != (stored_personal_id or '').strip().upper():
                    print("Personal ID verification failed.")
                    return

                password = getpass.getpass('Enter password: ')
                pass_query = "SELECT password FROM pass_table WHERE voter_id = %s"
                db.execute_query(pass_query, (voters_id,))
                pw_result = db.fetch_one()

                if pw_result:
                    stored_pwd = pw_result[0]
                    if verify_password(stored_pwd, password):
                        candidate_map = bc.display_mp(voters_id, mp_election_id)
                        if not candidate_map:
                            return

                        voter_choice = input("Cast vote (Enter Candidate Number) ->> ")
                        if voter_choice not in candidate_map:
                            print("Invalid choice.")
                            return

                        candidate_id = int(voter_choice)
                        timestamp = datetime.now().isoformat()
                        hmac_hash = compute_vote_hmac(voters_id, candidate_id, mp_election_id, timestamp)
                        ballot_id = generate_ballot_paper_id()

                        sql = """INSERT INTO votes(voter_id, candidate_id, election_id,
                                 polling_station_id, hmac_hash, ballot_paper_id)
                                 VALUES (%s, %s, %s, %s, %s, %s)"""
                        db.execute_query(sql, (voters_id, candidate_id, mp_election_id,
                                               polling_station_id, hmac_hash, ballot_id))

                        db.execute_query("UPDATE voterinfo SET mp_vote = %s WHERE voter_id = %s",
                                         (candidate_id, voters_id))

                        print(f"\nYour ballot paper ID is: {ballot_id}")
                        print("Please note this ID to verify your vote later.")
                        print("MP vote cast successfully!")

                        return vote_president(voters_id)
                    else:
                        print('Incorrect password.')
                else:
                    print('No password record found for this ID.')
            else:
                print("Sorry, but it seems you have casted your vote already")
    except Exception as e:
        print(f"An error occurred: {e}")


def vote_president(voters_id):
    try:
        pres_election_id = bc.get_presidential_election_id()
        if not pres_election_id:
            print("No active presidential election.")
            return

        if not require_phase(pres_election_id, 'voting'):
            return

        candidate_map = bc.display_presidents(pres_election_id)
        if not candidate_map:
            return

        voter_choice = input("Cast vote (Enter Candidate Number) ->> ")
        if voter_choice not in candidate_map:
            print("Invalid choice.")
            return

        candidate_id = int(voter_choice)

        with DatabaseManager() as db:
            db.execute_query("SELECT polling_station_id FROM voterinfo WHERE voter_id = %s", (voters_id,))
            row = db.fetch_one()
            polling_station_id = row[0] if row else None

            timestamp = datetime.now().isoformat()
            hmac_hash = compute_vote_hmac(voters_id, candidate_id, pres_election_id, timestamp)
            ballot_id = generate_ballot_paper_id()

            sql = """INSERT INTO votes(voter_id, candidate_id, election_id,
                     polling_station_id, hmac_hash, ballot_paper_id)
                     VALUES (%s, %s, %s, %s, %s, %s)"""
            db.execute_query(sql, (voters_id, candidate_id, pres_election_id,
                                   polling_station_id, hmac_hash, ballot_id))

            db.execute_query("UPDATE voterinfo SET president_vote = %s WHERE voter_id = %s",
                             (candidate_id, voters_id))
            db.execute_query("UPDATE voterinfo SET voted = 1 WHERE voter_id = %s", (voters_id,))

            print(f"\nYour ballot paper ID is: {ballot_id}")
            print("You can verify your vote at the results portal using this ID.")
            print("Vote successfully cast!")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def display_poll():
    while True:
        try:
            voter_entry = input("""Are you sure you want to vote now?
    1. Yes
    2. No\n""")
            if voter_entry == "1":
                vote_mp()
                break
            elif voter_entry == "2":
                print("You have chosen not to vote at this time.")
                break
            else:
                print("Invalid entry. Please enter 1 or 2.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
