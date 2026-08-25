"""Web-layer security: session secrets, CSRF protection, and auth dependencies."""

import os
import secrets

from fastapi import Form, HTTPException, Request

from rate_limiter import DatabaseRateLimiter

# --- Session secret -------------------------------------------------------------

INSECURE_SECRET_HINT = 'change-this-to-a-secure-random-key-in-production'


def get_session_secret() -> str:
    """Return SECRET_KEY from env, or an ephemeral key (dev only) when unset."""
    secret = os.getenv('SECRET_KEY', '')
    if not secret or secret == INSECURE_SECRET_HINT:
        # Ephemeral: sessions are invalidated on restart. Set SECRET_KEY in production.
        print('WARNING: SECRET_KEY is not set. Using an ephemeral key; all sessions will reset when the app restarts.')
        return secrets.token_hex(32)
    return secret


# --- Rate limiters --------------------------------------------------------------

admin_login_limiter = DatabaseRateLimiter(max_attempts=5, window_seconds=300)
voter_login_limiter = DatabaseRateLimiter(max_attempts=5, window_seconds=300)


def rate_limit_admin_login(request: Request, username: str = Form('')) -> None:
    key = f'admin:{username}:{request.client.host if request.client else "unknown"}'
    if not admin_login_limiter.is_allowed(key):
        raise HTTPException(status_code=429, detail='Too many login attempts. Try again in 5 minutes.')


def rate_limit_voter_login(request: Request, voter_id: str = Form('')) -> None:
    key = f'voter:{voter_id}:{request.client.host if request.client else "unknown"}'
    if not voter_login_limiter.is_allowed(key):
        raise HTTPException(status_code=429, detail='Too many login attempts. Try again in 5 minutes.')


# --- CSRF -----------------------------------------------------------------------


def get_csrf_token(request: Request) -> str:
    """Return the session's CSRF token, generating one on first use."""
    token = request.session.get('csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        request.session['csrf_token'] = token
    return token


def csrf(request: Request, csrf_token: str = Form('')) -> None:
    """Dependency: reject POSTs that do not carry the session's CSRF token."""
    expected = request.session.get('csrf_token')
    if not expected or not secrets.compare_digest(expected, csrf_token):
        raise HTTPException(status_code=400, detail='Invalid or missing CSRF token. Please go back and try again.')


# --- Auth dependencies -----------------------------------------------------------


def require_admin(request: Request) -> dict:
    """Dependency: redirect to the admin login page when no admin session exists."""
    admin = request.session.get('admin')
    if not admin:
        raise HTTPException(status_code=303, headers={'Location': '/admin/login'})
    return admin


def require_voter(request: Request) -> str:
    """Dependency: redirect to the voter login page when no voter session exists."""
    voter_id = request.session.get('voter_id')
    if not voter_id:
        raise HTTPException(status_code=303, headers={'Location': '/vote'})
    return voter_id
