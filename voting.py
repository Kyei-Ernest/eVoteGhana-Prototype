import ballot_creation as bc
import bcrypt
import getpass
from database import DatabaseManager

def verify_password(stored_password, provided_password):
    if isinstance(stored_password, str):
        stored_password = stored_password.encode('utf-8')
    return bcrypt.checkpw(provided_password.encode('utf-8'), stored_password)

def vote_mp():
    """Display the Member of Parliament candidates list and cast vote"""
    voters_id = input("Enter voter ID: ")
    
    try:
        with DatabaseManager() as db:
            votesql = "SELECT voted FROM voterinfo WHERE voter_id = %s"
            db.execute_query(votesql, (voters_id,))
            result = db.fetch_one()
            
            if not result:
                print("Voter ID not found.")
                return

            voted_already = result[0] # Boolean or 0/1

            if not voted_already:
                password = getpass.getpass('Enter password: ')
                pass_query = "SELECT password FROM pass_table WHERE voter_id = %s"
                db.execute_query(pass_query, (voters_id,))
                pw_result = db.fetch_one()
                
                if pw_result:
                    stored_pwd = pw_result[0]
                    # Verify password
                    if verify_password(stored_pwd, password):
                        candidate_map = bc.display_mp(voters_id)
                        
                        if not candidate_map:
                            print("No candidates available for your constituency.")
                            return
                        
                        voter_choice_mp = input("Cast vote (Enter Number) ->> ")
                        
                        if voter_choice_mp not in candidate_map:
                            print("Invalid choice.")
                            return
                        
                        mp_name = candidate_map[voter_choice_mp]
                        sql = "UPDATE voterinfo SET mp_vote = %s WHERE voter_id = %s"
                        db.execute_query(sql, (mp_name, voters_id))
                        
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
    """Display the presidential candidates list and cast vote"""
    try:
        bc.display_presidents()

        voter_choice_president = input("Cast vote (Enter ID number) ->> ")

        if not voter_choice_president or not voter_choice_president.isdigit():
             print("Invalid vote.")
             return

        with DatabaseManager() as db:
            db.execute_query("SELECT ID FROM presidents WHERE ID = %s", (voter_choice_president,))
            if not db.fetch_one():
                print("Invalid candidate ID.")
                return

            sql = "UPDATE voterinfo SET president_vote = %s WHERE voter_id = %s"
            db.execute_query(sql, (voter_choice_president, voters_id))

            sql_voted = "UPDATE voterinfo SET voted = 1 WHERE voter_id = %s"
            db.execute_query(sql_voted, (voters_id,))

            print("Vote successfully cast!")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def display_poll():
    """Voter's confirmation to take part in the election"""
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
