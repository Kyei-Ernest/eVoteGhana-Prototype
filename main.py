import Registration
import voting
import results_processing
import sys
from i18n import _
from admin_auth import validate_config, require_admin, logout_admin, is_admin_logged_in


def main_menu():
    validate_config()

    while True:
        status = " [ADMIN]" if is_admin_logged_in() else ""
        print(f"\n{_('welcome')}{status}")
        print(_('reg_setup'))
        print(_('cast_vote'))
        print(_('view_results'))
        print("5. Verify Vote by Ballot ID")
        print("6. Audit Trail")
        if is_admin_logged_in():
            print("7. Backup / Restore")
            print("8. Logout")
        else:
            print("7. Admin Login")
        print(_('exit'))

        choice = input(_('enter_choice'))

        if choice == '1':
            if require_admin():
                registration_menu()
        elif choice == '2':
            voting_menu()
        elif choice == '3':
            results_menu()
        elif choice == '4':
            print(_('exiting'))
            sys.exit()
        elif choice == '5':
            verify_vote_by_ballot()
        elif choice == '6':
            view_audit_trail()
        elif choice == '7':
            if is_admin_logged_in():
                backup_restore_menu()
            else:
                require_admin()
        elif choice == '8':
            if is_admin_logged_in():
                logout_admin()
            else:
                print(_('invalid_choice'))
        else:
            print(_('invalid_choice'))


def registration_menu():
    while True:
        print(f"\n{_('reg_menu')}")
        print(_('admin_setup'))
        print(_('voter_reg'))
        print(_('back'))

        choice = input(_('enter_choice'))

        if choice == '1':
            Registration.start_other_registration()
        elif choice == '2':
            Registration.start_voter_registration_process()
        elif choice == '3':
            break
        else:
            print(_('invalid_choice'))


def voting_menu():
    print(f"\n{_('voting_section')}")
    voting.display_poll()


def results_menu():
    print(f"\n{_('results_section')}")
    results_processing.display_results()


def verify_vote_by_ballot():
    ballot_id = input("Enter Ballot Paper ID (e.g., BALLOT-XXXX): ").strip()
    if not ballot_id:
        print("No ID entered.")
        return
    try:
        from database import DatabaseManager
        with DatabaseManager() as db:
            db.execute_query("""SELECT v.ballot_paper_id, v.created_at, c.name as candidate,
                                p.name as party, e.title as election, c2.name as constituency
                                FROM votes v
                                JOIN candidates c ON v.candidate_id = c.id
                                LEFT JOIN parties p ON c.party_id = p.id
                                LEFT JOIN constituencies c2 ON c.constituency_id = c2.id
                                JOIN elections e ON v.election_id = e.id
                                WHERE v.ballot_paper_id = %s""", (ballot_id,))
            row = db.fetch_one()
            if row:
                print("\n=== VOTE VERIFICATION ===")
                print(f"Ballot ID:    {row[0]}")
                print(f"Timestamp:    {row[1]}")
                print(f"Election:     {row[4]}")
                print(f"Candidate:    {row[2]}")
                print(f"Party:        {row[3] or 'Independent'}")
                if row[5]:
                    print(f"Constituency: {row[5]}")
                print("\nStatus: VERIFIED - This vote was recorded in the system.")
            else:
                print("\nBallot ID not found. Please check and try again.")
    except Exception as e:
        print(f"Error verifying vote: {e}")


def view_audit_trail():
    from audit_log import get_audit_trail
    logs = get_audit_trail(limit=50)
    if not logs:
        print("No audit records found.")
        return
    print("\n--- AUDIT TRAIL (Last 50 entries) ---")
    print(f"{'ID':<5} {'Action':<20} {'Table':<20} {'Record':<15} {'Actor':<15} {'Timestamp':<22}")
    print("-" * 97)
    for row in logs:
        print(f"{row[0]:<5} {row[1]:<20} {str(row[2] or ''):<20} "
              f"{str(row[3] or ''):<15} {str(row[4] or ''):<15} {str(row[6]):<22}")


def backup_restore_menu():
    from backup_restore import backup_database, restore_database
    print("\n1. Backup database")
    print("2. Restore database")
    sub = input("Choice: ")
    if sub == '1':
        backup_database()
    elif sub == '2':
        restore_database()
    else:
        print("Invalid choice.")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit()
