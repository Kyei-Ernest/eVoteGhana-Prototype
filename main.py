import Registration
import voting
import results_processing
import sys

def main_menu():
    while True:
        print("\n=== GHANA VOTING SYSTEM MAIN MENU ===")
        print("1. Registration & Setup (Admin/Voter)")
        print("2. Cast Vote")
        print("3. View Election Results")
        print("4. Exit")
        
        choice = input("Enter your choice: ")
        
        if choice == '1':
            registration_menu()
        elif choice == '2':
            voting_menu()
        elif choice == '3':
            results_menu()
        elif choice == '4':
            print("Exiting system. Goodbye!")
            sys.exit()
        else:
            print("Invalid choice. Please try again.")

def registration_menu():
    while True:
        print("\n--- Registration Menu ---")
        print("1. Administrative Setup (Candidates, Constituencies, MPs)")
        print("2. Voter Registration")
        print("3. Back to Main Menu")
        
        choice = input("Enter your choice: ")
        
        if choice == '1':
            Registration.start_other_registration()
        elif choice == '2':
            Registration.start_voter_registration_process()
        elif choice == '3':
            break
        else:
            print("Invalid choice.")

def voting_menu():
    print("\n--- Voting Section ---")
    voting.display_poll()

def results_menu():
    print("\n--- Election Results ---")
    results_processing.display_results()

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit()
