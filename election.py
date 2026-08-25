"""Election lifecycle management and constitutional result rules.

The election state machine is:

    nomination -> campaigning -> voting -> results -> closed

Transitions are forward-only, one or more steps ahead, and ``closed`` may only be
reached from ``results`` so results can never be bypassed. The module also hosts
the 50 percent + 1 threshold check from Article 63 of the 1992 Constitution of
Ghana and the runoff workflow that follows when no candidate meets it.
"""

from database import DatabaseManager

PHASES: list[str] = ['nomination', 'campaigning', 'voting', 'results', 'closed']
RUNOFF_CANDIDATE_COUNT = 2
VOTING_AGE = 18


def get_current_phase(election_id: int) -> str | None:
    """Return the effective phase, honouring scheduled start dates and auto-closing."""
    from datetime import date

    try:
        with DatabaseManager() as db:
            db.execute_query('SELECT phase, start_date, end_date FROM elections WHERE id = %s', (election_id,))
            row = db.fetch_one()
            if not row:
                return None
            phase, start_date, end_date = row
            today = date.today()
            if start_date and today < start_date and phase == 'voting':
                return 'scheduled'
            if end_date and today > end_date and phase == 'voting':
                auto_transition(election_id, 'results')
                return 'results'
            return phase
    except Exception as e:
        print(f'Error getting phase: {e}')
        return None


def _transition_allowed(current: str, new_phase: str) -> bool:
    """Forward-only rule; closing an election requires the results phase first.

    The pseudo-phase ``scheduled`` (start date in the future) counts as the first
    position so a scheduled election can still move into the normal lifecycle.
    """
    # 'scheduled' (start date not yet reached) ranks before 'nomination'.
    current_idx = PHASES.index(current) if current in PHASES else -1
    new_idx = PHASES.index(new_phase)
    if new_idx <= current_idx:
        return False
    return not (new_phase == 'closed' and current != 'results')


def transition_phase(election_id: int, new_phase: str) -> bool:
    if new_phase not in PHASES:
        print(f'Invalid phase: {new_phase}')
        return False
    try:
        with DatabaseManager() as db:
            current = get_current_phase(election_id)
            if current is None:
                print('Election not found.')
                return False
            if not _transition_allowed(current, new_phase):
                print(f'Cannot transition from {current} to {new_phase}.')
                from audit_log import log_action

                log_action('phase_transition_denied', 'elections', election_id, f'{current} -> {new_phase} rejected')
                return False
            db.execute_query('UPDATE elections SET phase = %s WHERE id = %s', (new_phase, election_id))
            from audit_log import log_action

            log_action('phase_transition', 'elections', election_id, f'{current} -> {new_phase}')
            print(f'Election {election_id} transitioned to {new_phase}.')
            return True
    except Exception as e:
        print(f'Error transitioning phase: {e}')
        return False


def auto_transition(election_id: int, new_phase: str) -> None:
    try:
        with DatabaseManager() as db:
            db.execute_query('UPDATE elections SET phase = %s WHERE id = %s', (new_phase, election_id))
    except Exception:
        pass


def require_phase(election_id: int, required_phase: str) -> bool:
    current = get_current_phase(election_id)
    if current != required_phase:
        print(f"This action requires the '{required_phase}' phase. Current phase: {current}")
        return False
    return True


def get_active_elections() -> list[tuple]:
    try:
        with DatabaseManager() as db:
            db.execute_query("SELECT id, title, position, phase FROM elections WHERE phase != 'closed'")
            return db.fetch_all()
    except Exception as e:
        print(f'Error fetching elections: {e}')
        return []


def check_50_percent_plus_one(total_votes: int, candidate_votes: int) -> bool:
    """True when a candidate has strictly more than half of all valid votes.

    Article 63(3) of the 1992 Constitution requires a presidential candidate to win
    more than 50 percent of the total valid votes cast, so exactly half is not enough.
    """
    if total_votes == 0:
        return False
    return candidate_votes > total_votes / 2


def needs_runoff(election_id: int) -> bool:
    """True when a presidential race has votes but no majority winner."""
    try:
        with DatabaseManager() as db:
            db.execute_query(
                'SELECT COUNT(*) FROM votes v JOIN candidates c ON v.candidate_id = c.id '
                'WHERE v.election_id = %s AND c.constituency_id IS NULL',
                (election_id,),
            )
            total = db.fetch_one()[0]
            if total == 0:
                return False
            top = _presidential_standings(db, election_id, limit=2)
            if not top:
                return False
            return not check_50_percent_plus_one(total, top[0][1])
    except Exception as e:
        print(f'Error checking runoff: {e}')
        return False


def presidential_top_two(election_id: int) -> list[tuple] | None:
    """Return the top two candidates as ``(candidate_id, votes, name, party_id)``
    when a runoff is required, otherwise ``None``."""
    try:
        with DatabaseManager() as db:
            db.execute_query(
                'SELECT COUNT(*) FROM votes v JOIN candidates c ON v.candidate_id = c.id '
                'WHERE v.election_id = %s AND c.constituency_id IS NULL',
                (election_id,),
            )
            total = db.fetch_one()[0]
            if total == 0:
                return None
            standings = _presidential_standings(db, election_id, limit=RUNOFF_CANDIDATE_COUNT)
            if len(standings) < RUNOFF_CANDIDATE_COUNT or check_50_percent_plus_one(total, standings[0][1]):
                return None
            return standings
    except Exception as e:
        print(f'Error finding runoff candidates: {e}')
        return None


def create_runoff_election(election_id: int, actor: str = 'system') -> int | None:
    """Create a fresh presidential election seeded with the top two candidates.

    Ghanaian law (Article 63(5)) requires a second round between the two leading
    candidates when no candidate achieves the majority threshold. This helper copies
    those two candidates into a new election titled ``"<original> Runoff"`` which
    starts in the nomination phase like any other election. Returns the new election
    id, or ``None`` when no runoff is warranted.
    """
    top_two = presidential_top_two(election_id)
    if not top_two:
        print('No runoff required for this election.')
        return None
    try:
        with DatabaseManager() as db:
            db.execute_query('SELECT title FROM elections WHERE id = %s', (election_id,))
            row = db.fetch_one()
            base_title = row[0] if row else f'Election {election_id}'
            runoff_title = f'{base_title} Runoff'
            db.execute_query(
                "INSERT INTO elections(title, position, phase) VALUES (%s, 'president', 'nomination')",
                (runoff_title,),
            )
            runoff_id = db.cursor.lastrowid
            for _candidate_id, _votes, name, party_id in top_two:
                db.execute_query(
                    'INSERT INTO candidates(name, party_id, election_id) VALUES (%s, %s, %s)',
                    (name, party_id, runoff_id),
                )
        from audit_log import log_action

        log_action(
            'runoff_created',
            'elections',
            runoff_id,
            f'Seeded from election {election_id}: {[name for _, _, name, _ in top_two]}',
            actor=actor,
        )
        print(f"Runoff election {runoff_id} '{runoff_title}' created.")
        return runoff_id
    except Exception as e:
        print(f'Error creating runoff election: {e}')
        return None


def _presidential_standings(db: DatabaseManager, election_id: int, limit: int = 2) -> list[tuple]:
    """Ranked presidential tallies: ``(candidate_id, votes, name, party_id)`` rows."""
    db.execute_query(
        'SELECT c.id, COUNT(*) AS cnt, c.name, c.party_id FROM votes v '
        'JOIN candidates c ON v.candidate_id = c.id '
        'WHERE v.election_id = %s AND c.constituency_id IS NULL '
        'GROUP BY c.id, c.name, c.party_id ORDER BY cnt DESC LIMIT %s',
        (election_id, limit),
    )
    return db.fetch_all()
