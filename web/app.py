"""eVoteGhana web application.

Serves the full election lifecycle over HTTP: voter registration, MFA voting,
ballot verification, results, and admin management. Reuses the existing business
logic modules (election, hmac_utils, rate_limiter, audit_log, results_processing,
ballot_creation) — only the CLI interaction layer is replaced with web forms.
"""

import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import bcrypt
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

import ballot_creation as bc_mod
import results_processing as rp
import validation as v
from age_calc import age
from audit_log import get_audit_trail, log_action
from database import DatabaseManager
from election import (
    PHASES,
    VOTING_AGE,
    check_50_percent_plus_one,
    create_runoff_election,
    get_current_phase,
    needs_runoff,
    transition_phase,
)
from hmac_utils import audit_votes_integrity, verify_vote_hmac
from rate_limiter import (
    db_voter_auth_limiter,
    db_voter_reg_limiter,
)
from Registration import RegisterVoter
from schema import SEED_REGIONS
from voting import claim_ballot_slot, maybe_mark_voting_complete, record_vote
from web import bootstrap, security

logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)
STATIONS_WITH_CONSTITUENCY_SQL = (
    'SELECT ps.id, ps.name, ps.code, c.name FROM polling_stations ps '
    'JOIN constituencies c ON ps.constituency_id = c.id ORDER BY c.name, ps.name'
)

RECENT_CANDIDATES_SQL = (
    'SELECT c.id, c.name, p.name, e.title FROM candidates c '
    'LEFT JOIN parties p ON c.party_id = p.id '
    'JOIN elections e ON c.election_id = e.id ORDER BY c.id DESC LIMIT 100'
)

PENDING_2FA_WINDOW_SECONDS = 300

logger = logging.getLogger('evote.web')

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / 'templates'))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    bootstrap.bootstrap()
    yield


app = FastAPI(
    title='eVoteGhana',
    docs_url='/docs' if os.getenv('ENABLE_DOCS', 'false').lower() == 'true' else None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=security.get_session_secret(),
    session_cookie='evote_session',
    max_age=int(os.getenv('SESSION_MAX_AGE', '1800')),
    same_site='lax',
    https_only=os.getenv('COOKIE_SECURE', 'false').lower() == 'true',
)
app.mount('/static', StaticFiles(directory=str(BASE_DIR / 'static')), name='static')


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add hardening headers and a request log line to every response."""

    async def dispatch(self, request: Request, call_next):
        start = datetime.now()
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; base-uri 'self'; frame-ancestors 'none'"
        )
        elapsed = (datetime.now() - start).total_seconds() * 1000
        logger.info('%s %s -> %s (%.1fms)', request.method, request.url.path, response.status_code, elapsed)
        return response


app.add_middleware(SecurityHeadersMiddleware)


# --- Render / flash helpers -----------------------------------------------------


def render(request: Request, template_name: str, status_code: int = 200, **ctx):
    ctx.setdefault('csrf_token', security.get_csrf_token(request))
    ctx.setdefault('admin', request.session.get('admin'))
    ctx.setdefault('voter_id', request.session.get('voter_id'))
    ctx.setdefault('lang', os.getenv('LANGUAGE', 'en'))
    ctx.setdefault('flash', request.session.pop('flash', []))
    return templates.TemplateResponse(request, template_name, ctx, status_code=status_code)


def flash(request: Request, message: str, kind: str = 'info') -> None:
    request.session.setdefault('flash', []).append({'kind': kind, 'message': message})


# --- Exception handlers ---------------------------------------------------------


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code in (301, 302, 303, 307, 308) and exc.headers and 'Location' in exc.headers:
        return RedirectResponse(exc.headers['Location'], status_code=exc.status_code)
    return render(request, 'error.html', code=exc.status_code, error=str(exc.detail), status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception('Unhandled error on %s', request.url.path)
    return render(request, 'error.html', code=500, error='An internal error occurred.', status_code=500)


# --- Public: home / health ------------------------------------------------------


@app.get('/', response_class=HTMLResponse)
def home(request: Request):
    return render(request, 'home.html')


@app.get('/healthz')
def healthz():
    ok = True
    try:
        with DatabaseManager() as db:
            db.execute_query('SELECT 1')
            db.fetch_one()
    except Exception as exc:  # noqa: BLE001
        logger.warning('Health check failed: %s', exc)
        ok = False
    status = 'ok' if ok else 'degraded'
    return JSONResponse({'status': status, 'time': datetime.now(UTC).isoformat()}, status_code=200 if ok else 503)


# --- Public: voter registration -------------------------------------------------


def _registration_errors(
    name, dob, contact, email, personal_id, occupation, constituency_id, polling_station_id, password, confirm
) -> tuple[dict, int]:
    errors: dict = {}
    legal_age = -1
    try:
        day, month, year = map(int, dob.split('/'))
        birth = datetime(year, month, day)
        legal_age = age(birth)
    except (ValueError, TypeError):
        errors['date_of_birth'] = 'Date of birth must be in DD/MM/YYYY format.'
    if legal_age < VOTING_AGE:
        errors['date_of_birth'] = f'Voter must be at least {VOTING_AGE} years old to register.'
    if not name or not str(name).strip():
        errors['name'] = 'Full name is required.'
    if not contact or not v.is_valid_contact(contact):
        errors['contact'] = 'Contact must be a valid 10-digit Ghanaian number starting with 0.'
    if email and not v.is_valid_email(email):
        errors['email'] = 'Invalid email format.'
    if personal_id and not v.is_valid_ghana_card(personal_id):
        errors['personal_id'] = 'Ghana Card ID must match format GHA-XXXXXXXXXX (10 alphanumeric).'
    if not occupation or not str(occupation).strip():
        errors['occupation'] = 'Occupation is required.'
    if password != confirm:
        errors['password'] = 'The passwords you entered do not match.'
    else:
        valid_pw, pw_msg = v.validate_password_strength(password)
        if not valid_pw:
            errors['password'] = pw_msg
    return errors, legal_age


@app.get('/register', response_class=HTMLResponse)
def register_page(request: Request):
    with DatabaseManager() as db:
        db.execute_query(
            'SELECT c.id, c.name, r.name FROM constituencies c JOIN regions r ON c.region_id = r.id ORDER BY c.name'
        )
        constituencies = db.fetch_all()
        db.execute_query(STATIONS_WITH_CONSTITUENCY_SQL)
        stations = db.fetch_all()
    return render(request, 'voter_register.html', constituencies=constituencies, stations=stations)


@app.post('/register', response_class=HTMLResponse)
def register_submit(
    request: Request,
    _csrf: None = Depends(security.csrf),
    name: str = Form(''),
    date_of_birth: str = Form(''),
    contact: str = Form(''),
    email: str = Form(''),
    personal_id: str = Form(''),
    occupation: str = Form(''),
    constituency_id: int = Form(...),
    polling_station_id: int = Form(...),
    password: str = Form(''),
    confirm_password: str = Form(''),
):
    client = request.client.host if request.client else 'unknown'
    if not db_voter_reg_limiter.is_allowed(f'reg:{client}'):
        flash(request, 'Too many registration attempts from this address. Try again later.', 'error')
        return RedirectResponse('/register', status_code=303)

    errors, _legal_age = _registration_errors(
        name,
        date_of_birth,
        contact,
        email,
        personal_id,
        occupation,
        constituency_id,
        polling_station_id,
        password,
        confirm_password,
    )

    with DatabaseManager() as db:
        db.execute_query('SELECT COUNT(*) FROM constituencies WHERE id = %s', (constituency_id,))
        if db.fetch_one()[0] == 0:
            errors['constituency_id'] = 'Selected constituency does not exist.'
        db.execute_query('SELECT COUNT(*) FROM polling_stations WHERE id = %s', (polling_station_id,))
        if db.fetch_one()[0] == 0:
            errors['polling_station_id'] = 'Selected polling station does not exist.'
        if personal_id:
            db.execute_query('SELECT COUNT(*) FROM voterinfo WHERE personal_id = %s', (personal_id,))
            if db.fetch_one()[0] > 0:
                errors['personal_id'] = 'This Ghana Card ID is already registered to another voter.'

    if errors:
        with DatabaseManager() as db:
            db.execute_query(
                'SELECT c.id, c.name, r.name FROM constituencies c JOIN regions r ON c.region_id = r.id ORDER BY c.name'
            )
            constituencies = db.fetch_all()
            db.execute_query(STATIONS_WITH_CONSTITUENCY_SQL)
            stations = db.fetch_all()
        return render(
            request,
            'voter_register.html',
            constituencies=constituencies,
            stations=stations,
            errors=errors,
            form={
                'name': name,
                'date_of_birth': date_of_birth,
                'contact': contact,
                'email': email,
                'personal_id': personal_id,
                'occupation': occupation,
                'constituency_id': constituency_id,
                'polling_station_id': polling_station_id,
            },
        )

    # Random 8-hex voter IDs can collide; retry with fresh IDs instead of failing.
    voter_id = None
    for _attempt in range(3):
        candidate_voter_id = secrets.token_hex(4).upper()
        with DatabaseManager() as db:
            db.execute_query('SELECT COUNT(*) FROM voterinfo WHERE voter_id = %s', (candidate_voter_id,))
            if db.fetch_one()[0] == 0:
                voter_id = candidate_voter_id
                break
    if voter_id is None:
        flash(request, 'Could not allocate a voter ID. Please try again.', 'error')
        return RedirectResponse('/register', status_code=303)

    svrp = RegisterVoter(
        voter_id=voter_id,
        name=name,
        date_of_birth=date_of_birth,
        contact=contact,
        email=email,
        personal_id=personal_id,
        occupation=occupation,
        constituency_id=constituency_id,
        polling_station_id=polling_station_id,
        password=password,
        conf_pass=confirm_password,
    )
    if not svrp.full_info():
        flash(request, 'Registration failed due to a database error. Please try again.', 'error')
        return RedirectResponse('/register', status_code=303)

    log_action('voter_registered_web', 'voterinfo', voter_id, f'Name: {name}')
    return render(request, 'voter_registered.html', voter_id=voter_id, name=name)


# --- Public: voting -------------------------------------------------------------


def _voter_row(voter_id: str) -> tuple | None:
    with DatabaseManager() as db:
        db.execute_query(
            'SELECT voted, mp_vote, president_vote, personal_id, constituency_id FROM voterinfo WHERE voter_id = %s',
            (voter_id,),
        )
        return db.fetch_one()


def _candidates_for(election_id: int, constituency_id: int | None) -> list[tuple]:
    with DatabaseManager() as db:
        if constituency_id is None:
            db.execute_query(
                'SELECT c.id, c.name, p.name, p.abbreviation FROM candidates c '
                'LEFT JOIN parties p ON c.party_id = p.id '
                'WHERE c.election_id = %s AND c.constituency_id IS NULL ORDER BY c.id',
                (election_id,),
            )
        else:
            db.execute_query(
                'SELECT c.id, c.name, p.name, p.abbreviation FROM candidates c '
                'LEFT JOIN parties p ON c.party_id = p.id '
                'WHERE c.election_id = %s AND c.constituency_id = %s ORDER BY c.id',
                (election_id, constituency_id),
            )
        return db.fetch_all()


def _ballot_state(voter_id: str, row: tuple) -> dict:
    """Decide which ballots are available for this voter right now."""
    _voted, mp_vote, president_vote, _personal_id, constituency_id = row

    mp_election_id = bc_mod.get_mp_election_id()
    pres_election_id = bc_mod.get_presidential_election_id()

    mp_ballot = None
    if mp_election_id and not mp_vote and get_current_phase(mp_election_id) == 'voting':
        candidates = _candidates_for(mp_election_id, constituency_id)
        if candidates:
            mp_ballot = {'election_id': mp_election_id, 'candidates': candidates}

    pres_ballot = None
    if pres_election_id and not president_vote and get_current_phase(pres_election_id) == 'voting':
        candidates = _candidates_for(pres_election_id, None)
        if candidates:
            pres_ballot = {'election_id': pres_election_id, 'candidates': candidates}

    return {'mp': mp_ballot, 'president': pres_ballot}


@app.get('/vote', response_class=HTMLResponse)
def vote_home(request: Request):
    voter_id = request.session.get('voter_id')
    if not voter_id:
        return render(request, 'voter_login.html')

    row = _voter_row(voter_id)
    if row is None:
        request.session.pop('voter_id', None)
        flash(request, 'Voter record not found. Please log in again.', 'error')
        return render(request, 'voter_login.html')

    if row[0]:  # already voted
        ballots = request.session.get('ballots', [])
        return render(request, 'vote_done.html', ballots=ballots)

    return render(request, 'vote.html', ballots=_ballot_state(voter_id, row))


@app.post('/vote/login', response_class=HTMLResponse)
def vote_login(
    request: Request,
    _csrf: None = Depends(security.csrf),
    _rl: None = Depends(security.rate_limit_voter_login),
    voter_id: str = Form(''),
    password: str = Form(''),
):
    voter_id = voter_id.strip().upper()
    with DatabaseManager() as db:
        db.execute_query('SELECT password FROM pass_table WHERE voter_id = %s', (voter_id,))
        pw_row = db.fetch_one()
        db.execute_query('SELECT voter_id FROM voterinfo WHERE voter_id = %s', (voter_id,))
        exists = db.fetch_one()

    if not exists or not pw_row or not bcrypt.checkpw(password.encode('utf-8'), pw_row[0].encode('utf-8')):
        flash(request, 'Invalid voter ID or password.', 'error')
        return render(request, 'voter_login.html')

    request.session['voter_id'] = voter_id
    log_action('voter_login', 'voterinfo', voter_id, 'Voter logged in')
    return RedirectResponse('/vote', status_code=303)


@app.post('/vote/logout', response_class=HTMLResponse)
def vote_logout(request: Request, _csrf: None = Depends(security.csrf)):
    request.session.pop('voter_id', None)
    request.session.pop('ballots', None)
    return RedirectResponse('/', status_code=303)


def _cast_ballot(request: Request, candidate_id: int, personal_id: str, position: str) -> RedirectResponse:
    """Shared ballot-casting logic for MP and presidential votes."""
    voter_id = request.session.get('voter_id')
    if not voter_id:
        return RedirectResponse('/vote', status_code=303)
    if not db_voter_auth_limiter.is_allowed(voter_id):
        flash(request, 'Too many attempts. Try again in 5 minutes.', 'error')
        return RedirectResponse('/vote', status_code=303)

    row = _voter_row(voter_id)
    if row is None:
        request.session.pop('voter_id', None)
        return RedirectResponse('/vote', status_code=303)
    if row[0]:
        flash(request, 'You have already cast your vote.', 'error')
        return RedirectResponse('/vote', status_code=303)

    # MFA: the Ghana Card personal ID must match the one on record.
    if personal_id.strip().upper() != (row[3] or '').strip().upper():
        flash(request, 'Ghana Card verification failed. Your ballot was not recorded.', 'error')
        return RedirectResponse('/vote', status_code=303)

    election_id = bc_mod.get_mp_election_id() if position == 'mp' else bc_mod.get_presidential_election_id()
    if not election_id:
        flash(request, 'No active election for this ballot.', 'error')
        return RedirectResponse('/vote', status_code=303)
    if get_current_phase(election_id) != 'voting':
        flash(request, 'Voting is not open for this election.', 'error')
        return RedirectResponse('/vote', status_code=303)

    constituency_id = row[4]
    allowed = _candidates_for(election_id, constituency_id if position == 'mp' else None)
    if candidate_id not in [c[0] for c in allowed]:
        flash(request, 'Invalid candidate selection. Your ballot was not recorded.', 'error')
        return RedirectResponse('/vote', status_code=303)

    with DatabaseManager() as db:
        # The conditional UPDATE makes double-voting impossible even when two
        # requests arrive simultaneously: only one can flip the NULL slot.
        if not claim_ballot_slot(db, voter_id, position):
            flash(request, 'Your ballot for this race was already recorded.', 'error')
            return RedirectResponse('/vote', status_code=303)
        ballot_id = record_vote(db, voter_id, candidate_id, election_id)
        maybe_mark_voting_complete(db, voter_id)

    log_action('vote_cast', 'votes', ballot_id, f'{position} ballot for election {election_id}', actor=voter_id)

    ballots = request.session.setdefault('ballots', [])
    ballots.append({'position': position, 'ballot_id': ballot_id})
    flash(request, f'{position.title()} ballot recorded. Your ballot paper ID: {ballot_id}')
    return RedirectResponse('/vote', status_code=303)


@app.post('/vote/mp', response_class=HTMLResponse)
def vote_mp_submit(
    request: Request,
    _csrf: None = Depends(security.csrf),
    candidate_id: int = Form(...),
    personal_id: str = Form(''),
):
    return _cast_ballot(request, candidate_id, personal_id, 'mp')


@app.post('/vote/president', response_class=HTMLResponse)
def vote_president_submit(
    request: Request,
    _csrf: None = Depends(security.csrf),
    candidate_id: int = Form(...),
    personal_id: str = Form(''),
):
    return _cast_ballot(request, candidate_id, personal_id, 'president')


# --- Public: ballot verification ------------------------------------------------


@app.get('/verify', response_class=HTMLResponse)
def verify_page(request: Request):
    return render(request, 'ballot_verify.html')


@app.post('/verify', response_class=HTMLResponse)
def verify_submit(
    request: Request,
    _csrf: None = Depends(security.csrf),
    ballot_id: str = Form(''),
):
    ballot_id = ballot_id.strip()
    if not ballot_id:
        return render(request, 'ballot_verify.html', result=None, error='Please enter a ballot paper ID.')

    with DatabaseManager() as db:
        db.execute_query(
            'SELECT v.ballot_paper_id, v.created_at, c.name, p.name, e.title, c2.name, '
            'v.candidate_id, v.election_id, v.hmac_hash, v.key_version, v.polling_station_id '
            'FROM votes v '
            'JOIN candidates c ON v.candidate_id = c.id '
            'LEFT JOIN parties p ON c.party_id = p.id '
            'LEFT JOIN constituencies c2 ON c.constituency_id = c2.id '
            'JOIN elections e ON v.election_id = e.id '
            'WHERE v.ballot_paper_id = %s',
            (ballot_id,),
        )
        row = db.fetch_one()

    if not row:
        return render(
            request, 'ballot_verify.html', result=None, error='Ballot ID not found. Please check and try again.'
        )
    display_row = row[:6]
    signature_ok = verify_vote_hmac(row[7], row[6], row[0], row[8], row[9] or 'k1', row[10])
    return render(request, 'ballot_verify.html', result=display_row, signature_ok=signature_ok)


# --- Public: results ------------------------------------------------------------


@app.get('/results', response_class=HTMLResponse)
def results_page(request: Request):
    with DatabaseManager() as db:
        db.execute_query(
            "SELECT id, title, position, phase FROM elections WHERE phase IN ('results', 'closed') ORDER BY id"
        )
        elections = db.fetch_all()

    elections_data = []
    for eid, title, position, phase in elections:
        turnout = rp.collate_turnout(eid)
        entry = {
            'id': eid,
            'title': title,
            'position': position,
            'phase': phase,
            'turnout': turnout,
        }
        if position == 'president':
            pres = rp.collate_presidential_results(eid)
            entry['total'] = pres['total']
            entry['rows'] = pres['results']
            entry['runoff'] = needs_runoff(eid)
            entry['winner'] = None
            if pres['results'] and check_50_percent_plus_one(pres['total'], pres['results'][0][3]):
                entry['winner'] = pres['results'][0][1]
        else:
            mp = rp.collate_mp_results(eid)
            regional = rp.collate_regional_results(eid)
            entry['constituencies'] = list(mp.values())
            entry['regional'] = regional
        elections_data.append(entry)

    return render(request, 'results.html', elections=elections_data)


# --- Admin: auth ----------------------------------------------------------------


@app.get('/admin/login', response_class=HTMLResponse)
def admin_login_page(request: Request):
    if request.session.get('admin'):
        return RedirectResponse('/admin', status_code=303)
    return render(request, 'admin_login.html')


@app.post('/admin/login', response_class=HTMLResponse)
def admin_login(
    request: Request,
    _csrf: None = Depends(security.csrf),
    _rl: None = Depends(security.rate_limit_admin_login),
    username: str = Form(''),
    password: str = Form(''),
):
    with DatabaseManager() as db:
        db.execute_query(
            'SELECT password_hash, role, totp_secret, totp_enabled FROM admins WHERE username = %s',
            (username.strip(),),
        )
        row = db.fetch_one()

    if not row or not bcrypt.checkpw(password.encode('utf-8'), row[0].encode('utf-8')):
        flash(request, 'Invalid credentials.', 'error')
        return render(request, 'admin_login.html')

    _password_hash, role, totp_secret, totp_enabled = row
    if totp_enabled and totp_secret:
        # Password factor passed; hold the session in a pending state until the
        # code factor completes. Nothing privileged is reachable meanwhile.
        request.session['pending_2fa'] = {
            'username': username.strip(),
            'role': role,
            'at': datetime.now(UTC).timestamp(),
        }
        return RedirectResponse('/admin/login/2fa', status_code=303)

    request.session['admin'] = {'username': username.strip(), 'role': role}
    log_action('admin_login', 'admins', username.strip(), f'Role: {role}', actor=username.strip())
    return RedirectResponse('/admin', status_code=303)


@app.get('/admin/login/2fa', response_class=HTMLResponse)
def admin_twofa_page(request: Request):
    if not request.session.get('pending_2fa'):
        return RedirectResponse('/admin/login', status_code=303)
    return render(request, 'admin_twofa.html')


@app.post('/admin/login/2fa', response_class=HTMLResponse)
def admin_twofa_submit(
    request: Request,
    _csrf: None = Depends(security.csrf),
    _rl: None = Depends(security.rate_limit_admin_login),
    code: str = Form(''),
):
    pending = request.session.get('pending_2fa')
    if not pending:
        return RedirectResponse('/admin/login', status_code=303)
    age = datetime.now(UTC).timestamp() - float(pending.get('at', 0))
    if age > PENDING_2FA_WINDOW_SECONDS:
        request.session.pop('pending_2fa', None)
        flash(request, 'Two factor window expired. Please sign in again.', 'error')
        return RedirectResponse('/admin/login', status_code=303)

    import pyotp

    with DatabaseManager() as db:
        db.execute_query('SELECT totp_secret, totp_enabled FROM admins WHERE username = %s', (pending['username'],))
        row = db.fetch_one()
    if not row or not row[1] or not pyotp.TOTP(row[0]).verify(code.strip(), valid_window=1):
        log_action('admin_2fa_failed', 'admins', pending['username'], 'Invalid or expired code')
        flash(request, 'Invalid authentication code.', 'error')
        return render(request, 'admin_twofa.html')

    username, role = pending['username'], pending['role']
    request.session.pop('pending_2fa', None)
    request.session['admin'] = {'username': username, 'role': role}
    log_action('admin_login', 'admins', username, f'Role: {role} (2FA)', actor=username)
    return RedirectResponse('/admin', status_code=303)


@app.get('/admin/security', response_class=HTMLResponse)
def admin_security_page(request: Request, admin: dict = Depends(security.require_admin)):
    import pyotp

    username = admin['username']
    with DatabaseManager() as db:
        db.execute_query('SELECT totp_secret, totp_enabled FROM admins WHERE username = %s', (username,))
        row = db.fetch_one()

    secret, enabled = row if row else (None, False)
    provisioning_uri = None
    if not enabled:
        if not secret:
            secret = pyotp.random_base32()
            with DatabaseManager() as db:
                db.execute_query('UPDATE admins SET totp_secret = %s WHERE username = %s', (secret, username))
            log_action('admin_totp_secret_generated', 'admins', username, 'Pending enrollment')
        provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=username, issuer_name=os.getenv('TOTP_ISSUER', 'eVoteGhana')
        )
    return render(
        request, 'admin_security.html', admin=admin, enabled=enabled, secret=secret, provisioning_uri=provisioning_uri
    )


@app.post('/admin/security/totp/enable', response_class=HTMLResponse)
def admin_totp_enable(
    request: Request,
    _admin: dict = Depends(security.require_admin),
    _csrf: None = Depends(security.csrf),
    code: str = Form(''),
):
    import pyotp

    username = _admin['username']
    with DatabaseManager() as db:
        db.execute_query('SELECT totp_secret FROM admins WHERE username = %s', (username,))
        row = db.fetch_one()
        secret = row[0] if row else None
        if not secret or not pyotp.TOTP(secret).verify(code.strip(), valid_window=1):
            flash(request, 'Enrollment failed: the code did not match the shown secret.', 'error')
            return RedirectResponse('/admin/security', status_code=303)
        db.execute_query('UPDATE admins SET totp_enabled = 1 WHERE username = %s', (username,))
    log_action('admin_totp_enabled', 'admins', username, 'Second factor active', actor=username)
    flash(request, 'Two factor authentication is now active for your account.')
    return RedirectResponse('/admin/security', status_code=303)


@app.post('/admin/security/totp/disable', response_class=HTMLResponse)
def admin_totp_disable(
    request: Request,
    _admin: dict = Depends(security.require_admin),
    _csrf: None = Depends(security.csrf),
    code: str = Form(''),
):
    import pyotp

    username = _admin['username']
    with DatabaseManager() as db:
        db.execute_query('SELECT totp_secret, totp_enabled FROM admins WHERE username = %s', (username,))
        row = db.fetch_one()
        secret, enabled = row if row else (None, False)
        if not enabled or not secret or not pyotp.TOTP(secret).verify(code.strip(), valid_window=1):
            flash(request, 'Disable failed: provide a current authentication code.', 'error')
            return RedirectResponse('/admin/security', status_code=303)
        db.execute_query('UPDATE admins SET totp_enabled = 0, totp_secret = NULL WHERE username = %s', (username,))
    log_action('admin_totp_disabled', 'admins', username, 'Second factor removed', actor=username)
    flash(request, 'Two factor authentication has been removed from your account.')
    return RedirectResponse('/admin/security', status_code=303)


@app.post('/admin/logout', response_class=HTMLResponse)
def admin_logout(request: Request, _csrf: None = Depends(security.csrf)):
    request.session.pop('admin', None)
    return RedirectResponse('/', status_code=303)


# --- Admin: dashboard -----------------------------------------------------------


@app.get('/admin', response_class=HTMLResponse)
def admin_dashboard(request: Request, admin: dict = Depends(security.require_admin)):
    with DatabaseManager() as db:
        db.execute_query('SELECT id, title, position, phase FROM elections ORDER BY id DESC LIMIT 50')
        elections = db.fetch_all()
        db.execute_query('SELECT COUNT(*) FROM voterinfo')
        voter_count = db.fetch_one()[0]
        db.execute_query('SELECT COUNT(*) FROM votes')
        vote_count = db.fetch_one()[0]
        db.execute_query('SELECT COUNT(*) FROM candidates')
        candidate_count = db.fetch_one()[0]
    return render(
        request,
        'admin_dashboard.html',
        admin=admin,
        elections=elections,
        voter_count=voter_count,
        vote_count=vote_count,
        candidate_count=candidate_count,
    )


@app.post('/admin/elections/create', response_class=HTMLResponse)
def admin_election_create(
    request: Request,
    _admin: dict = Depends(security.require_admin),
    _csrf: None = Depends(security.csrf),
    title: str = Form(''),
    position: str = Form(''),
):
    position = position.strip().lower()
    if position not in ('president', 'mp'):
        flash(request, 'Position must be president or mp.', 'error')
        return RedirectResponse('/admin', status_code=303)
    with DatabaseManager() as db:
        db.execute_query(
            "INSERT INTO elections(title, position, phase) VALUES (%s, %s, 'nomination')", (title, position)
        )
        eid = db.cursor.lastrowid
    log_action(
        'election_created', 'elections', eid, f'{title} ({position})', actor=request.session['admin']['username']
    )
    flash(request, f"Election '{title}' created.")
    return RedirectResponse('/admin', status_code=303)


@app.post('/admin/elections/transition', response_class=HTMLResponse)
def admin_election_transition(
    request: Request,
    _admin: dict = Depends(security.require_admin),
    _csrf: None = Depends(security.csrf),
    election_id: int = Form(...),
    new_phase: str = Form(''),
):
    new_phase = new_phase.strip().lower()
    if new_phase not in PHASES:
        flash(request, f'Invalid phase: {new_phase}', 'error')
    elif transition_phase(election_id, new_phase):
        flash(request, f'Election {election_id} moved to {new_phase}.')
    else:
        flash(request, f'Could not move election {election_id} to {new_phase}.', 'error')
    return RedirectResponse('/admin', status_code=303)


@app.post('/admin/elections/runoff', response_class=HTMLResponse)
def admin_election_runoff(
    request: Request,
    _admin: dict = Depends(security.require_admin),
    _csrf: None = Depends(security.csrf),
    election_id: int = Form(...),
):
    actor = request.session['admin']['username']
    runoff_id = create_runoff_election(election_id, actor=actor)
    if runoff_id:
        flash(request, f'Runoff election {runoff_id} created from election {election_id} with the top two candidates.')
    else:
        flash(request, f'No runoff needed or possible for election {election_id}.', 'error')
    return RedirectResponse('/admin', status_code=303)


# --- Admin: setup (regions, constituencies, stations, parties, candidates) ------


@app.get('/admin/setup', response_class=HTMLResponse)
def admin_setup(request: Request, admin: dict = Depends(security.require_admin)):
    with DatabaseManager() as db:
        db.execute_query('SELECT id, name FROM regions ORDER BY name')
        regions = db.fetch_all()
        db.execute_query(
            'SELECT c.id, c.name, r.name FROM constituencies c JOIN regions r ON c.region_id = r.id ORDER BY c.name'
        )
        constituencies = db.fetch_all()
        db.execute_query(STATIONS_WITH_CONSTITUENCY_SQL)
        stations = db.fetch_all()
        db.execute_query('SELECT id, name, abbreviation FROM parties ORDER BY name')
        parties = db.fetch_all()
        db.execute_query('SELECT id, title, position, phase FROM elections ORDER BY id')
        elections = db.fetch_all()
        db.execute_query(RECENT_CANDIDATES_SQL)
        candidates = db.fetch_all()
    return render(
        request,
        'admin_setup.html',
        admin=admin,
        regions=regions,
        constituencies=constituencies,
        stations=stations,
        parties=parties,
        elections=elections,
        candidates=candidates,
    )


@app.post('/admin/regions/seed', response_class=HTMLResponse)
def admin_regions_seed(
    request: Request,
    _admin: dict = Depends(security.require_admin),
    _csrf: None = Depends(security.csrf),
):
    with DatabaseManager() as db:
        db.execute_query('SELECT COUNT(*) FROM regions')
        existing = db.fetch_one()[0]
        if existing == 0:
            db.execute_query(SEED_REGIONS)
            flash(request, 'All 16 regions of Ghana added.')
        else:
            flash(request, 'Regions already exist.', 'info')
    return RedirectResponse('/admin/setup', status_code=303)


@app.post('/admin/constituencies/add', response_class=HTMLResponse)
def admin_constituency_add(
    request: Request,
    _admin: dict = Depends(security.require_admin),
    _csrf: None = Depends(security.csrf),
    name: str = Form(''),
    region_id: int = Form(...),
):
    with DatabaseManager() as db:
        db.execute_query('INSERT INTO constituencies(name, region_id) VALUES (%s, %s)', (name, region_id))
        cid = db.cursor.lastrowid
    log_action('constituency_added', 'constituencies', cid, name, actor=request.session['admin']['username'])
    flash(request, f"Constituency '{name}' added.")
    return RedirectResponse('/admin/setup', status_code=303)


@app.post('/admin/stations/add', response_class=HTMLResponse)
def admin_station_add(
    request: Request,
    _admin: dict = Depends(security.require_admin),
    _csrf: None = Depends(security.csrf),
    name: str = Form(''),
    code: str = Form(''),
    constituency_id: int = Form(...),
):
    with DatabaseManager() as db:
        db.execute_query(
            'INSERT INTO polling_stations(name, code, constituency_id) VALUES (%s, %s, %s)',
            (name, code, constituency_id),
        )
        psid = db.cursor.lastrowid
    log_action(
        'polling_station_added',
        'polling_stations',
        psid,
        f'{name} ({code})',
        actor=request.session['admin']['username'],
    )
    flash(request, f"Polling station '{name}' added.")
    return RedirectResponse('/admin/setup', status_code=303)


@app.post('/admin/parties/add', response_class=HTMLResponse)
def admin_party_add(
    request: Request,
    _admin: dict = Depends(security.require_admin),
    _csrf: None = Depends(security.csrf),
    name: str = Form(''),
    abbreviation: str = Form(''),
):
    with DatabaseManager() as db:
        db.execute_query('INSERT INTO parties(name, abbreviation) VALUES (%s, %s)', (name, abbreviation))
        pid = db.cursor.lastrowid
    log_action('party_added', 'parties', pid, name, actor=request.session['admin']['username'])
    flash(request, f"Party '{name}' added.")
    return RedirectResponse('/admin/setup', status_code=303)


@app.post('/admin/candidates/president/add', response_class=HTMLResponse)
def admin_presidential_candidate_add(
    request: Request,
    _admin: dict = Depends(security.require_admin),
    _csrf: None = Depends(security.csrf),
    name: str = Form(''),
    party_id: int = Form(...),
    election_id: int = Form(...),
):
    with DatabaseManager() as db:
        db.execute_query(
            'INSERT INTO candidates(name, party_id, election_id) VALUES (%s, %s, %s)', (name, party_id, election_id)
        )
        cid = db.cursor.lastrowid
    log_action('candidate_added', 'candidates', cid, f'President: {name}', actor=request.session['admin']['username'])
    flash(request, f"Presidential candidate '{name}' added.")
    return RedirectResponse('/admin/setup', status_code=303)


@app.post('/admin/candidates/mp/add', response_class=HTMLResponse)
def admin_mp_candidate_add(
    request: Request,
    _admin: dict = Depends(security.require_admin),
    _csrf: None = Depends(security.csrf),
    name: str = Form(''),
    party_id: int = Form(...),
    election_id: int = Form(...),
    constituency_id: int = Form(...),
):
    with DatabaseManager() as db:
        if party_id == 0:
            db.execute_query(
                'INSERT INTO candidates(name, constituency_id, election_id) VALUES (%s, %s, %s)',
                (name, constituency_id, election_id),
            )
        else:
            db.execute_query(
                'INSERT INTO candidates(name, party_id, constituency_id, election_id) VALUES (%s, %s, %s, %s)',
                (name, party_id, constituency_id, election_id),
            )
        cid = db.cursor.lastrowid
    log_action('candidate_added', 'candidates', cid, f'MP: {name}', actor=request.session['admin']['username'])
    flash(request, f"MP candidate '{name}' added.")
    return RedirectResponse('/admin/setup', status_code=303)


# --- Admin: voters, audit, backup -----------------------------------------------


@app.get('/admin/voters', response_class=HTMLResponse)
def admin_voters(request: Request, admin: dict = Depends(security.require_admin)):
    with DatabaseManager() as db:
        db.execute_query(
            'SELECT v.voter_id, v.name, v.personal_id, v.voted, c.name, ps.name '
            'FROM voterinfo v '
            'LEFT JOIN constituencies c ON v.constituency_id = c.id '
            'LEFT JOIN polling_stations ps ON v.polling_station_id = ps.id '
            'ORDER BY v.created_at DESC LIMIT 500',
        )
        voters = db.fetch_all()
    return render(request, 'admin_voters.html', admin=admin, voters=voters)


@app.get('/admin/audit', response_class=HTMLResponse)
def admin_audit(request: Request, admin: dict = Depends(security.require_admin)):
    from audit_log import verify_audit_chain

    logs = get_audit_trail(limit=200)
    chain = verify_audit_chain()
    integrity = audit_votes_integrity(limit=5000)
    return render(request, 'admin_audit.html', admin=admin, logs=logs, chain=chain, integrity=integrity)


@app.get('/admin/backup', response_class=HTMLResponse)
def admin_backup_page(request: Request, admin: dict = Depends(security.require_admin)):
    return render(request, 'admin_backup.html', admin=admin)


@app.post('/admin/backup', response_class=HTMLResponse)
def admin_backup_run(
    request: Request,
    _admin: dict = Depends(security.require_admin),
    _csrf: None = Depends(security.csrf),
):
    import backup_restore

    backup_restore.backup_database()
    flash(request, 'Backup requested. Check the backups/ directory for the file.')
    return RedirectResponse('/admin/backup', status_code=303)
