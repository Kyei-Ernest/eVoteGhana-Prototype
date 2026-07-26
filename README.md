# Ghana Voting System (Python)

A Python-based electronic voting system prototype tailored for the Ghanaian electoral context. This project demonstrates a complete election lifecycle including voter registration with Ghana Card verification, candidate registration (Presidential & MP), ballot casting, and automatic result tabulation.

## 🚀 Features

- **Voter Registration**: Captures strict details (ID, Name, DOB with age verification, Constituency).
- **Security**: 
  - **Password Hashing**: Uses `bcrypt` for secure password storage.
  - **Secure Input**: Passwords are hidden during entry.
  - **Environment Variables**: Database credentials are managed via `.env`.
- **Candidate Management**: Supports registering Political Parties, Presidential candidates, and MPs per constituency.
- **Voting Process**: 
  - Constituency-based logic (Voters only see MPs for their constituency).
  - One-man-one-vote enforcement.
- **Results**: Automated tabulation of votes with percentage calculations.

## 🛠️ Prerequisites

- **Python 3.8+**
- **MySQL Server**

## 📦 Installation & Setup

1.  **Clone/Download the repository**


2.  **Create & Activate Virtual Environment**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment**
    - The project comes with a default `.env` file.
    - Open `.env` and update the `DB_PASSWORD` and `DB_USER` to match your local MySQL setup.
    ```ini
    DB_HOST=127.0.0.1
    DB_USER=root
    DB_PASSWORD=your_password
    DB_NAME_MAIN=mydb
    ```

4.  **Initialize Database**
    Run the schema script to create the necessary database and tables:
    ```bash
    python3 schema.py
    ```

## 🖥️ Usage

### 1. Run the Application
Use the unified entry point to access all features:
```bash
python3 main.py
```
From the main menu, you can navigate to:
- **Registration**: Setup candidates/constituencies or register voters.
- **Voting**: Cast ballots (requires Voter ID and Password).
- **Results**: specific election outcomes.

Alternatively, you can run individual modules:

### Registration Phase
**Recommended Order:**
1.  **Add Presidential Candidates**: Option `1` in "Other Registration".
2.  **Add Constituencies**: Option `2`.
3.  **Add Parliamentary (MP) Candidates**: Option `3` (Link them to constituencies).
4.  **Register Voters**: Run the script again and choose `Start Voter Registration`.

### 2. Voting Phase
Voters cast their ballots using the voting module:
```bash
python3 voting.py
```
- Users will be prompted for their Voter ID and Password.
- They will vote for an MP (specific to their constituency) and a President.

### 3. Results Phase
View the election outcomes:
```bash
python3 results_processing.py
```

## 📂 Project Structure

- **`Registration.py`**: Main script for registering voters and candidates.
- **`voting.py`**: Interface for casting votes.
- **`results_processing.py`**: Calculates and displays election results.
- **`schema.py`**: Handles database initialization.
- **`database.py`**: Centralized database connection manager.
- **`config.py`**: Loads settings from environment variables.
- **`ballot_creation.py`**: Helper to display candidates on the ballot.
- **`age_calc.py`**: Utility for age verification.

---
*Note: This is a prototype system designed for educational and demonstration purposes.*
