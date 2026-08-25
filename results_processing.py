"""Result collation: constituency, regional, and national tallies with turnout.

Implements the arithmetic behind the EC Ghana result forms:

    Form 1A  presidential summary per candidate plus majority/runoff verdict
    Form 1C  parliamentary summary per constituency (first past the post)

Turnout is reported against the full registered voter roll, which is how the EC
presents national participation figures for a general election.
"""

from database import DatabaseManager
from election import RUNOFF_CANDIDATE_COUNT, check_50_percent_plus_one


def collate_presidential_results(election_id: int) -> dict:
    try:
        with DatabaseManager() as db:
            db.execute_query('SELECT COUNT(*) FROM votes WHERE election_id = %s', (election_id,))
            total_votes = db.fetch_one()[0]

            db.execute_query(
                'SELECT v.candidate_id, c.name, p.name as party, COUNT(*) as cnt FROM votes v '
                'JOIN candidates c ON v.candidate_id = c.id '
                'LEFT JOIN parties p ON c.party_id = p.id '
                'WHERE v.election_id = %s AND c.constituency_id IS NULL '
                'GROUP BY v.candidate_id, c.name, p.name ORDER BY cnt DESC',
                (election_id,),
            )
            results = db.fetch_all()

            return {'total': total_votes, 'results': results}
    except Exception as e:
        print(f'Error collating presidential results: {e}')
        return {'total': 0, 'results': []}


def collate_mp_results(election_id: int) -> dict:
    try:
        with DatabaseManager() as db:
            db.execute_query(
                'SELECT DISTINCT c.constituency_id, con.name as const_name, r.name as region_name '
                'FROM candidates c JOIN constituencies con ON c.constituency_id = con.id '
                'JOIN regions r ON con.region_id = r.id WHERE c.election_id = %s ORDER BY r.name, con.name',
                (election_id,),
            )
            constituencies = db.fetch_all()

            results_by_constituency: dict = {}
            for const_id, const_name, region_name in constituencies:
                db.execute_query(
                    'SELECT v.candidate_id, c.name, p.name as party, COUNT(*) as cnt FROM votes v '
                    'JOIN candidates c ON v.candidate_id = c.id '
                    'LEFT JOIN parties p ON c.party_id = p.id '
                    'WHERE v.election_id = %s AND c.constituency_id = %s '
                    'GROUP BY v.candidate_id, c.name, p.name ORDER BY cnt DESC',
                    (election_id, const_id),
                )
                cand_results = db.fetch_all()
                results_by_constituency[const_id] = {
                    'name': const_name,
                    'region': region_name,
                    'results': cand_results,
                }

            return results_by_constituency
    except Exception as e:
        print(f'Error collating MP results: {e}')
        return {}


def collate_regional_results(election_id: int) -> list[tuple]:
    try:
        with DatabaseManager() as db:
            db.execute_query(
                'SELECT r.id, r.name, COUNT(*) as total FROM votes v '
                'JOIN candidates c ON v.candidate_id = c.id '
                'JOIN constituencies con ON c.constituency_id = con.id '
                'JOIN regions r ON con.region_id = r.id '
                'WHERE v.election_id = %s AND c.constituency_id IS NOT NULL '
                'GROUP BY r.id, r.name ORDER BY r.name',
                (election_id,),
            )
            return db.fetch_all()
    except Exception as e:
        print(f'Error collating regional results: {e}')
        return []


def collate_turnout(election_id: int) -> dict:
    """Registered voters versus ballots cast for one election.

    Returns ``{'registered', 'cast', 'turnout_pct'}``. Ballots cast counts distinct
    voters so a voter who voted in both races still counts once toward participation.
    """
    try:
        with DatabaseManager() as db:
            db.execute_query('SELECT COUNT(*) FROM voterinfo')
            registered = db.fetch_one()[0]
            db.execute_query('SELECT COUNT(DISTINCT voter_id) FROM votes WHERE election_id = %s', (election_id,))
            cast = db.fetch_one()[0]
            pct = round(cast / registered * 100, 1) if registered else 0.0
            return {'registered': registered, 'cast': cast, 'turnout_pct': pct}
    except Exception as e:
        print(f'Error computing turnout: {e}')
        return {'registered': 0, 'cast': 0, 'turnout_pct': 0.0}


def format_form_1a(election_id: int, results: dict) -> None:
    print('\n' + '=' * 60)
    print('            EC GHANA FORM 1A - PRESIDENTIAL RESULTS')
    print('=' * 60)
    print(f'{"Candidate":<25} {"Party":<15} {"Votes":<10} {"%":<8}')
    print('-' * 60)
    for row in results['results']:
        name, party, count = row[1], row[2], row[3]
        pct = round((count / results['total'] * 100), 1) if results['total'] > 0 else 0
        print(f'{name:<25} {party or "IND":<15} {count:<10} {pct:<8}%')
    print('-' * 60)
    print(f'{"Total Valid Votes":<40} {results["total"]:<10}')
    print('=' * 60)

    if results['results'] and check_50_percent_plus_one(results['total'], results['results'][0][3]):
        winner = results['results'][0][1]
        party = results['results'][0][2] or ''
        print(f'\nWINNER: {winner} ({party}) - 50%+1 threshold achieved')
    elif len(results['results']) >= RUNOFF_CANDIDATE_COUNT:
        print('\nNO WINNER: Runoff required')
        print(f'Top two: {results["results"][0][1]} vs {results["results"][1][1]}')


def format_form_1c(constituency_name: str, results: list[tuple], region_name: str = '') -> None:
    print('\n' + '-' * 60)
    print(f'     EC GHANA FORM 1C - PARLIAMENTARY: {constituency_name}')
    if region_name:
        print(f'     Region: {region_name}')
    print('-' * 60)
    print(f'{"Candidate":<25} {"Party":<15} {"Votes":<10}')
    print('-' * 60)
    total = 0
    for row in results:
        name, party, count = row[1], row[2], row[3]
        total += count
        print(f'{name:<25} {party or "IND":<15} {count:<10}')
    print('-' * 60)
    print(f'{"Total Valid Votes":<40} {total:<10}')
    print('-' * 60)


def display_results() -> None:
    from election import needs_runoff

    try:
        with DatabaseManager() as db:
            db.execute_query(
                "SELECT id, title, position, phase FROM elections WHERE phase IN ('results', 'closed') ORDER BY id",
            )
            elections = db.fetch_all()

            if not elections:
                print('No completed elections found.')
                return

            from audit_log import log_action

            for e in elections:
                eid, title, position, phase = e
                print(f'\n{"=" * 60}')
                print(f'  ELECTION: {title} ({position})')
                print('=' * 60)

                if position == 'president':
                    pres_results = collate_presidential_results(eid)
                    format_form_1a(eid, pres_results)
                    if needs_runoff(eid):
                        print('\n*** PRESIDENTIAL RUNOFF REQUIRED ***')
                        print('No candidate achieved the constitutional 50%+1 threshold.')
                    log_action('results_viewed', 'elections', eid, 'Presidential results displayed')

                elif position == 'mp':
                    mp_results = collate_mp_results(eid)
                    regional = collate_regional_results(eid)
                    for _const_id, data in mp_results.items():
                        format_form_1c(data['name'], data['results'], data['region'])
                    if regional:
                        print('\n' + '=' * 60)
                        print('  REGIONAL SUMMARY')
                        print('=' * 60)
                        print(f'{"Region":<20} {"Votes Cast":<12}')
                        print('-' * 32)
                        for r in regional:
                            print(f'{r[1]:<20} {r[2]:<12}')
                    log_action('results_viewed', 'elections', eid, 'MP results displayed')

    except Exception as err:
        print(f'Error displaying results: {err}')
