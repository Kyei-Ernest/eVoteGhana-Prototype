import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch


def _capturing_conn():
    conn = MagicMock()
    state = {'rows': []}

    def execute(query, params=None):
        q = ' '.join(query.split()).upper()
        if q.startswith('SELECT ENTRY_HASH'):
            conn.fetch_one.return_value = (state['rows'][-1][7],) if state['rows'] else None
        elif q.startswith('INSERT INTO AUDIT_LOG') and params:
            prev_hash, entry_hash, created_at = params[5], params[6], params[7]
            from audit_log import _entry_hash

            recomputed = _entry_hash(prev_hash, params[0], params[1], params[2], params[3], params[4], created_at)
            assert recomputed == entry_hash
            state['rows'].append((len(state['rows']) + 1, *params[:5], prev_hash, entry_hash, created_at))

    conn.execute_query.side_effect = execute
    return conn, state


class TestChainedWrites:
    @patch('audit_log.DatabaseManager')
    def test_second_entry_links_to_first(self, mock_db):
        from audit_log import log_action

        conn, state = _capturing_conn()
        mock_db.return_value.__enter__.return_value = conn

        log_action('action_one', 'elections', 1, 'first', actor='admin')
        log_action('action_two', 'elections', 2, 'second', actor='admin')

        first_prev, second_prev = state['rows'][0][6], state['rows'][1][6]
        assert first_prev == '0' * 64
        assert second_prev == state['rows'][0][7]


class TestChainVerification:
    @patch('audit_log.DatabaseManager')
    def test_intact_chain_verifies(self, mock_db):
        from hashlib import sha256

        from audit_log import GENESIS_HASH, _entry_hash, verify_audit_chain

        rows = []
        prev = GENESIS_HASH
        for i in (1, 2, 3):
            ts = f'2026-08-25T00:00:0{i}.000000+00:00'
            entry_hash = _entry_hash(prev, f'act{i}', f't{i}', str(i), f'd{i}', 'sys', ts)
            assert entry_hash == sha256(f'{prev}|act{i}|t{i}|{i}|d{i}|sys|{ts}'.encode()).hexdigest()
            rows.append((i, f'act{i}', f't{i}', str(i), f'd{i}', 'sys', prev, entry_hash, ts))
            prev = entry_hash

        conn = MagicMock()
        conn.fetch_all.return_value = rows
        mock_db.return_value.__enter__.return_value = conn

        report = verify_audit_chain()
        assert report['ok'] is True
        assert report['checked'] == 3
        assert report['broken_after'] is None

    @patch('audit_log.DatabaseManager')
    def test_tampered_content_breaks_chain(self, mock_db):
        """Editing a historical details field is detected even with triggers bypassed."""
        from audit_log import GENESIS_HASH, _entry_hash, verify_audit_chain

        rows = []
        prev = GENESIS_HASH
        for i in (1, 2):
            ts = f'2026-08-25T00:00:0{i}.000000+00:00'
            entry_hash = _entry_hash(prev, f'act{i}', f't{i}', str(i), f'd{i}', 'sys', ts)
            rows.append((i, f'act{i}', f't{i}', str(i), f'd{i}', 'sys', prev, entry_hash, ts))
            prev = entry_hash

        entry_id, action, table_name, record_id, _details, actor, prev_hash, entry_hash, ts = rows[0]
        tampered = list(rows)
        tampered[0] = (entry_id, action, table_name, record_id, 'REWRITTEN DETAILS', actor, prev_hash, entry_hash, ts)

        conn = MagicMock()
        conn.fetch_all.return_value = tampered
        mock_db.return_value.__enter__.return_value = conn

        report = verify_audit_chain()
        assert report['ok'] is False
        assert report['broken_after'] == 0
