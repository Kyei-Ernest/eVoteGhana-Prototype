import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """TestClient with bootstrap disabled (no real DB needed)."""
    with patch('web.app.bootstrap.bootstrap'):
        from web.app import app

        with TestClient(app) as c:
            yield c


def test_home_renders(client):
    resp = client.get('/')
    assert resp.status_code == 200
    assert 'eVoteGhana' in resp.text
    assert 'Voter Registration' in resp.text


def test_healthz_ok(client):
    with patch('web.app.DatabaseManager') as mock_db:
        mock_db.return_value.__enter__.return_value = MagicMock()
        resp = client.get('/healthz')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'ok'


def test_vote_page_shows_login_when_anonymous(client):
    resp = client.get('/vote')
    assert resp.status_code == 200
    assert 'Voter Login' in resp.text


def test_admin_redirects_when_not_logged_in(client):
    resp = client.get('/admin', follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers['location'] == '/admin/login'


def test_register_page_renders(client):
    with patch('web.app.DatabaseManager') as mock_db:
        conn = MagicMock()
        conn.fetch_all.return_value = [(1, 'Ashanti', 'Ashanti Region')]
        mock_db.return_value.__enter__.return_value = conn
        resp = client.get('/register')
    assert resp.status_code == 200
    assert 'Voter Registration' in resp.text


def test_post_without_csrf_token_rejected(client):
    resp = client.post('/register', data={'name': 'x'})
    assert resp.status_code == 400


def test_verify_page_renders(client):
    resp = client.get('/verify')
    assert resp.status_code == 200
    assert 'Verify a Vote by Ballot ID' in resp.text


def test_results_page_renders(client):
    with (
        patch('web.app.DatabaseManager') as mock_db,
        patch(
            'web.app.rp.collate_presidential_results',
            return_value={
                'total': 10,
                'results': [(1, 'Candidate A', 'NPP', 6), (2, 'Candidate B', 'NDC', 4)],
            },
        ),
        patch('web.app.needs_runoff', return_value=False),
    ):
        conn = MagicMock()
        conn.fetch_all.return_value = [(1, '2024 General Election', 'president', 'results')]
        mock_db.return_value.__enter__.return_value = conn
        resp = client.get('/results')
    assert resp.status_code == 200
    assert '2024 General Election' in resp.text
    assert 'Candidate A' in resp.text
    assert 'WINNER' in resp.text


def test_admin_login_page_renders(client):
    resp = client.get('/admin/login')
    assert resp.status_code == 200
    assert 'Admin Login' in resp.text
