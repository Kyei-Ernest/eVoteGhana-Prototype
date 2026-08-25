"""Terminal ballot casting with MFA, HMAC integrity, and atomic vote claims.

The critical safety property lives in :func:`claim_ballot_slot`: instead of the
classic ``SELECT`` then ``INSERT`` pattern (a time-of-check-to-time-of-use race),
each ballot slot is reserved with a single conditional ``UPDATE`` guarded on the
slot still being ``NULL``. InnoDB serialises concurrent updates on the row lock,
so exactly one request can win the reservation even under simultaneous submits.
"""

import getpass

import bcrypt

import ballot_creation as bc
from database import DatabaseManager
from election import require_phase
from hmac_utils import compute_vote_hmac, generate_ballot_paper_id
from rate_limiter import voter_auth_limiter

BALLOT_SLOTS: dict[str, str] = {'mp': 'mp_vote', 'president': 'president_vote'}


def verify_password(stored_password: str | bytes, provided_password: str) -> bool:
    if isinstance(stored_password, str):
        stored_password = stored_password.encode('utf-8')
    return bcrypt.checkpw(provided_password.encode('utf-8'), stored_password)


def claim_ballot_slot(db: DatabaseManager, voter_id: str, position: str, candidate_id: int) -> bool:
    """Atomically reserve the voter's ballot slot for ``position``.

    Returns True when this call won the reservation; False means the slot was
    already used, so the vote must be rejected. Must run inside the transaction
    that also inserts the signed vote row.
    """
    column = BALLOT_SLOTS[position]
    db.execute_query(
        f'UPDATE voterinfo SET {column} = %s WHERE voter_id = %s AND {column} IS NULL',
        (candidate_id, voter_id),
    )
    return db.cursor.rowcount == 1


def record_vote(db: DatabaseManager, voter_id: str, candidate_id: int, election_id: int) -> str:
    """Insert the HMAC-signed vote row and return its public ballot paper ID."""
    ballot_id = generate_ballot_paper_id()
    hmac_hash = compute_vote_hmac(voter_id, candidate_id, election_id, ballot_id)
    db.execute_query(
        'INSERT INTO votes(voter_id, candidate_id, election_id, polling_station_id, hmac_hash, ballot_paper_id) '
        'VALUES (%s, %s, %s, (SELECT polling_station_id FROM voterinfo WHERE voter_id = %s), %s, %s)',
        (voter_id, candidate_id, election_id, voter_id, hmac_hash, ballot_id),
    )
    return ballot_id


def maybe_mark_voting_complete(db: DatabaseManager, voter_id: str) -> None:
    """Flag the voter as finished once every open ballot slot has been used.

    A voter who has cast both ballots, or whose remaining slot has no election
    currently open, will not be prompted again on their next visit.
    """
    db.execute_query('SELECT mp_vote, president_vote FROM voterinfo WHERE voter_id = %s', (voter_id,))
    row = db.fetch_one()
    if not row:
        return
    mp_vote, president_vote = row
    mp_pending = mp_vote is None and bc.get_mp_election_id() is not None
    pres_pending = president_vote is None and bc.get_presidential_election_id() is not None
    if not mp_pending and not pres_pending:
        db.execute_query('UPDATE voterinfo SET voted = 1 WHERE voter_id = %s', (voter_id,))


def vote_mp() -> None:
    voters_id = input('Enter voter ID: ')

    if not voter_auth_limiter.is_allowed(voters_id):
        print('Too many attempts. Try again in 5 minutes.')
        return

    try:
        with DatabaseManager() as db:
            mp_election_id = bc.get_mp_election_id()
            if not mp_election_id:
                print('No active MP election.')
                return

            if not require_phase(mp_election_id, 'voting'):
                return

            db.execute_query(
                'SELECT voted, polling_station_id, personal_id FROM voterinfo WHERE voter_id = %s',
                (voters_id,),
            )
            result = db.fetch_one()

            if not result:
                print('Voter ID not found.')
                return

            voted_already, _polling_station_id, stored_personal_id = result

            if voted_already:
                print('Sorry, but it seems you have casted your vote already')
                return

            personal_id_verify = getpass.getpass('Enter Ghana Card (Personal ID) for verification: ')
            if personal_id_verify.strip().upper() != (stored_personal_id or '').strip().upper():
                print('Personal ID verification failed.')
                return

            password = getpass.getpass('Enter password: ')
            db.execute_query('SELECT password FROM pass_table WHERE voter_id = %s', (voters_id,))
            pw_result = db.fetch_one()

            if not pw_result:
                print('No password record found for this ID.')
                return

            if not verify_password(pw_result[0], password):
                print('Incorrect password.')
                return

            candidate_map = bc.display_mp(voters_id, mp_election_id)
            if not candidate_map:
                return

            voter_choice = input('Cast vote (Enter Candidate Number) ->> ')
            if voter_choice not in candidate_map:
                print('Invalid choice.')
                return

            candidate_id = int(voter_choice)
            if not claim_ballot_slot(db, voters_id, 'mp', candidate_id):
                print('Your MP ballot was already recorded.')
                return
            ballot_id = record_vote(db, voters_id, candidate_id, mp_election_id)

            print(f'\nYour ballot paper ID is: {ballot_id}')
            print('Please note this ID to verify your vote later.')
            print('MP vote cast successfully!')

            return vote_president(voters_id)
    except Exception as e:
        print(f'An error occurred: {e}')


def vote_president(voters_id: str) -> None:
    try:
        pres_election_id = bc.get_presidential_election_id()
        if not pres_election_id:
            print('No active presidential election.')
            return

        if not require_phase(pres_election_id, 'voting'):
            return

        candidate_map = bc.display_presidents(pres_election_id)
        if not candidate_map:
            return

        voter_choice = input('Cast vote (Enter Candidate Number) ->> ')
        if voter_choice not in candidate_map:
            print('Invalid choice.')
            return

        candidate_id = int(voter_choice)

        with DatabaseManager() as db:
            if not claim_ballot_slot(db, voters_id, 'president', candidate_id):
                print('Your presidential ballot was already recorded.')
                return
            ballot_id = record_vote(db, voters_id, candidate_id, pres_election_id)
            maybe_mark_voting_complete(db, voters_id)

            print(f'\nYour ballot paper ID is: {ballot_id}')
            print('You can verify your vote at the results portal using this ID.')
            print('Vote successfully cast!')
    except Exception as e:
        print(f'An unexpected error occurred: {e}')


def display_poll() -> None:
    while True:
        try:
            voter_entry = input('Are you sure you want to vote now?\n1. Yes\n2. No\n')
            if voter_entry == '1':
                vote_mp()
                break
            elif voter_entry == '2':
                print('You have chosen not to vote at this time.')
                break
            else:
                print('Invalid entry. Please enter 1 or 2.')
        except Exception as e:
            print(f'An unexpected error occurred: {e}')
