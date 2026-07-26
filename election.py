from database import DatabaseManager
from datetime import date, datetime


PHASES = ['nomination', 'campaigning', 'voting', 'results', 'closed']


def get_current_phase(election_id):
    try:
        with DatabaseManager() as db:
            db.execute_query("SELECT phase, start_date, end_date FROM elections WHERE id = %s", (election_id,))
            row = db.fetch_one()
            if not row:
                return None
            phase, start_date, end_date = row
            today = date.today()
            if start_date and today < start_date:
                return 'scheduled'
            if end_date and today > end_date and phase == 'voting':
                auto_transition(election_id, 'results')
                return 'results'
            return phase
    except Exception as e:
        print(f"Error getting phase: {e}")
        return None


def transition_phase(election_id, new_phase):
    if new_phase not in PHASES:
        print(f"Invalid phase: {new_phase}")
        return False
    try:
        with DatabaseManager() as db:
            current = get_current_phase(election_id)
            if current is None:
                print("Election not found.")
                return False
            current_idx = PHASES.index(current) if current in PHASES else -1
            new_idx = PHASES.index(new_phase)
            if new_idx <= current_idx and new_phase != 'closed':
                print(f"Cannot transition from {current} to {new_phase}.")
                return False
            db.execute_query("UPDATE elections SET phase = %s WHERE id = %s", (new_phase, election_id))
            from audit_log import log_action
            log_action('phase_transition', 'elections', election_id, f"{current} -> {new_phase}")
            print(f"Election {election_id} transitioned to {new_phase}.")
            return True
    except Exception as e:
        print(f"Error transitioning phase: {e}")
        return False


def auto_transition(election_id, new_phase):
    try:
        with DatabaseManager() as db:
            db.execute_query("UPDATE elections SET phase = %s WHERE id = %s", (new_phase, election_id))
    except Exception:
        pass


def require_phase(election_id, required_phase):
    current = get_current_phase(election_id)
    if current != required_phase:
        print(f"This action requires the '{required_phase}' phase. Current phase: {current}")
        return False
    return True


def get_active_elections():
    try:
        with DatabaseManager() as db:
            db.execute_query("SELECT id, title, position, phase FROM elections WHERE phase != 'closed'")
            return db.fetch_all()
    except Exception as e:
        print(f"Error fetching elections: {e}")
        return []


def check_50_percent_plus_one(total_votes, candidate_votes):
    if total_votes == 0:
        return False
    threshold = total_votes / 2
    return candidate_votes > threshold


def needs_runoff(election_id):
    try:
        with DatabaseManager() as db:
            db.execute_query("""SELECT COUNT(*) FROM votes v
                                JOIN candidates c ON v.candidate_id = c.id
                                WHERE v.election_id = %s AND c.constituency_id IS NULL""",
                             (election_id,))
            total = db.fetch_one()[0]
            if total == 0:
                return False
            db.execute_query("""SELECT v.candidate_id, COUNT(*) as cnt FROM votes v
                                JOIN candidates c ON v.candidate_id = c.id
                                WHERE v.election_id = %s AND c.constituency_id IS NULL
                                GROUP BY v.candidate_id ORDER BY cnt DESC LIMIT 1""",
                             (election_id,))
            top = db.fetch_one()
            if not top:
                return False
            return not check_50_percent_plus_one(total, top[1])
    except Exception as e:
        print(f"Error checking runoff: {e}")
        return False
