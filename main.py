import Registration
import voting
import results_processing
import sys
from i18n import _


def main_menu():
    while True:
        print(f"\n{_('welcome')}")
        print(_('reg_setup'))
        print(_('cast_vote'))
        print(_('view_results'))
        print("5. Audit Trail")
        print(_('exit'))

        choice = input(_('enter_choice'))

        if choice == '1':
            registration_menu()
        elif choice == '2':
            voting_menu()
        elif choice == '3':
            results_menu()
        elif choice == '4':
            print(_('exiting'))
            sys.exit()
        elif choice == '5':
            view_audit_trail()
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


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit()
