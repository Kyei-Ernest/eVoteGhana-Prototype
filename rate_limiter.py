import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        self.attempts[key] = [t for t in self.attempts[key] if now - t < self.window_seconds]
        if len(self.attempts[key]) >= self.max_attempts:
            return False
        self.attempts[key].append(now)
        return True

    def remaining_attempts(self, key: str) -> int:
        now = time.time()
        self.attempts[key] = [t for t in self.attempts[key] if now - t < self.window_seconds]
        return max(0, self.max_attempts - len(self.attempts[key]))


class DatabaseRateLimiter:
    """Sliding window limiter whose counters live in MySQL, shared by every worker.

    Each attempt runs inside one transaction: the bucket row is locked with
    SELECT ... FOR UPDATE, evaluated, and updated or inserted. On any database
    failure the limiter fails OPEN with a logged warning, trading a short abuse
    window for continued availability of the login endpoints.
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds

    def _fail_open(self, key: str, exc: Exception) -> bool:
        import logging

        logging.getLogger('evote.ratelimit').warning(
            'Rate limiter failing open for %s after database error: %s', key[:32], exc
        )
        return True

    def is_allowed(self, key: str) -> bool:
        from database import DatabaseManager

        try:
            with DatabaseManager() as db:
                db.execute_query(
                    'SELECT hits, TIMESTAMPDIFF(SECOND, window_start, NOW()) FROM rate_limit_buckets '
                    'WHERE bucket = %s FOR UPDATE',
                    (key,),
                )
                row = db.fetch_one()
                if row is None:
                    db.execute_query(
                        'INSERT INTO rate_limit_buckets(bucket, hits, window_start) VALUES (%s, 1, NOW())',
                        (key,),
                    )
                    return True
                hits, age_seconds = row
                if age_seconds is None or age_seconds >= self.window_seconds:
                    db.execute_query(
                        'UPDATE rate_limit_buckets SET hits = 1, window_start = NOW() WHERE bucket = %s',
                        (key,),
                    )
                    return True
                if hits >= self.max_attempts:
                    return False
                db.execute_query('UPDATE rate_limit_buckets SET hits = hits + 1 WHERE bucket = %s', (key,))
                return True
        except Exception as exc:  # noqa: BLE001
            return self._fail_open(key, exc)

    def remaining_attempts(self, key: str) -> int:
        from database import DatabaseManager

        try:
            with DatabaseManager() as db:
                db.execute_query(
                    'SELECT hits, TIMESTAMPDIFF(SECOND, window_start, NOW()) FROM rate_limit_buckets WHERE bucket = %s',
                    (key,),
                )
                row = db.fetch_one()
                if row is None:
                    return self.max_attempts
                hits, age_seconds = row
                if age_seconds is not None and age_seconds >= self.window_seconds:
                    return self.max_attempts
                return max(0, self.max_attempts - hits)
        except Exception:  # noqa: BLE001
            return self.max_attempts


# Terminal interface keeps process local counters because the CLI is single user.
voter_auth_limiter: RateLimiter = RateLimiter(max_attempts=5, window_seconds=300)
voter_reg_limiter: RateLimiter = RateLimiter(max_attempts=10, window_seconds=3600)

# Web application limiters share state across uvicorn workers through the database.
db_voter_auth_limiter = DatabaseRateLimiter(max_attempts=5, window_seconds=300)
db_admin_login_limiter = DatabaseRateLimiter(max_attempts=5, window_seconds=300)
db_voter_login_limiter = DatabaseRateLimiter(max_attempts=5, window_seconds=300)
db_voter_reg_limiter = DatabaseRateLimiter(max_attempts=10, window_seconds=3600)
