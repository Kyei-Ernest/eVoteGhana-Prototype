import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, max_attempts=5, window_seconds=300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts = defaultdict(list)

    def is_allowed(self, key):
        now = time.time()
        self.attempts[key] = [t for t in self.attempts[key] if now - t < self.window_seconds]
        if len(self.attempts[key]) >= self.max_attempts:
            return False
        self.attempts[key].append(now)
        return True

    def remaining_attempts(self, key):
        now = time.time()
        self.attempts[key] = [t for t in self.attempts[key] if now - t < self.window_seconds]
        return max(0, self.max_attempts - len(self.attempts[key]))


voter_auth_limiter = RateLimiter(max_attempts=5, window_seconds=300)
voter_reg_limiter = RateLimiter(max_attempts=10, window_seconds=3600)
