from database import DatabaseManager


def get_presidential_election_id() -> int | None:
    try:
        with DatabaseManager() as db:
            db.execute_query("SELECT id FROM elections WHERE position = 'president' AND phase = 'voting' ORDER BY id DESC LIMIT 1")
            row = db.fetch_one()
            return row[0] if row else None
    except Exception as e:
        print(f"Error: {e}")
        return None


def get_mp_election_id() -> int | None:
    try:
        with DatabaseManager() as db:
            db.execute_query("SELECT id FROM elections WHERE position = 'mp' AND phase = 'voting' ORDER BY id DESC LIMIT 1")
            row = db.fetch_one()
            return row[0] if row else None
    except Exception as e:
        print(f"Error: {e}")
        return None


def display_presidents(election_id: int | None = None) -> dict[str, str]:
    try:
        if election_id is None:
            election_id = get_presidential_election_id()
        if election_id is None:
            print("No active presidential election.")
            return {}

        with DatabaseManager() as db:
            db.execute_query("SELECT c.id, c.name, p.name, p.abbreviation FROM candidates c LEFT JOIN parties p ON c.party_id = p.id WHERE c.election_id = %s AND c.constituency_id IS NULL ORDER BY c.id", (election_id,))
            candidates = db.fetch_all()

            if not candidates:
                print("No presidential candidates found.")
                return {}

            print("** Vote for your preferred presidential candidate **")
            candidate_map: dict[str, str] = {}
            for c in candidates:
                print(f"{c[0]}: {c[1]} ({c[2] or 'Independent'})")
                candidate_map[str(c[0])] = c[1]
            return candidate_map
    except Exception as e:
        print(f"Error displaying candidates: {e}")
        return {}


def display_mp(voter_id: str, election_id: int | None = None) -> dict[str, str]:
    try:
        if election_id is None:
            election_id = get_mp_election_id()
        if election_id is None:
            print("No active MP election.")
            return {}

        with DatabaseManager() as db:
            db.execute_query("SELECT constituency_id, polling_station_id FROM voterinfo WHERE voter_id = %s", (voter_id,))
            voter = db.fetch_one()
            if not voter:
                print("Voter not found.")
                return {}
            constituency_id = voter[0]

            db.execute_query("SELECT name FROM constituencies WHERE id = %s", (constituency_id,))
            const_row = db.fetch_one()
            const_name = const_row[0] if const_row else "Unknown"

            print(f"** Vote for your preferred MP for {const_name} **")

            db.execute_query("SELECT c.id, c.name, p.name, p.abbreviation FROM candidates c LEFT JOIN parties p ON c.party_id = p.id WHERE c.election_id = %s AND c.constituency_id = %s ORDER BY c.id", (election_id, constituency_id))
            candidates = db.fetch_all()

            if not candidates:
                print(f"No MP candidates found for {const_name}.")
                return {}

            candidate_map: dict[str, str] = {}
            for c in candidates:
                party = c[2] or "Independent"
                abbr = c[3] or ""
                print(f"{c[0]}: {c[1]} ({party} {abbr})".strip())
                candidate_map[str(c[0])] = c[1]
            return candidate_map
    except Exception as e:
        print(f"Error in display_mp: {e}")
        return {}
