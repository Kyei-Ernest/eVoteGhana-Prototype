import mysql_value_checker as vc
from database import DatabaseManager

def display_presidents():
    """Display presidential candidates to voter"""
    try:
        print("** Vote for your preferred presidential candidate **")
        with DatabaseManager() as db:
            sql1 = "SELECT ID, political_party, presidential_candidate_name FROM presidents"
            db.execute_query(sql1)
            myr1 = db.fetch_all()
            for x, y, z in myr1:
                print(f"{x} {y} - {z}")
    except Exception as e:
        print(f"Error while retrieving presidential candidates: {e}")


def display_mp(voter_id):
    """Check the existence of the voter file and display MPs for the voter's constituency.
    Returns a dict mapping display numbers to candidate names."""
    candidate_map = {}
    try:
        voterid_exists = vc.check_value_exists(table='voterinfo', column='voter_id', user_input=voter_id)

        if voterid_exists:
            print("ID successfully verified\n")

            with DatabaseManager() as db:
                query_constituency = "SELECT constituency FROM voterinfo WHERE voter_id = %s"
                db.execute_query(query_constituency, (voter_id,))
                constituencies = db.fetch_all()

                for constituency in constituencies:
                    constituency_name = constituency[0]
                    print(f"** Vote for your preferred MP for {constituency_name} **")

                    query_mps = "SELECT * FROM members_of_parliament WHERE constituency = %s"
                    db.execute_query(query_mps, (constituency_name,))
                    mps = db.fetch_one()
                    
                    if mps:
                        count = 0
                        candidates = mps[2:]
                        for mp in candidates:
                            count += 1
                            if mp:
                                print(f"{count}. {mp}")
                                candidate_map[str(count)] = mp
                    else:
                        print(f"No MPs found for constituency {constituency_name}")

        else:
            print("Sorry, you have entered an invalid id. Try again")
            
    except Exception as e:
        print(f"Error in display_mp: {e}")
    
    return candidate_map
