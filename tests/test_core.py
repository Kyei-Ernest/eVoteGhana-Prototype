import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from election import check_50_percent_plus_one


class TestElection:
    def test_50_percent_plus_one_achieved(self):
        assert check_50_percent_plus_one(100, 51) is True

    def test_50_percent_plus_one_exact_half(self):
        assert check_50_percent_plus_one(100, 50) is False

    def test_50_percent_plus_one_less_than_half(self):
        assert check_50_percent_plus_one(100, 49) is False

    def test_50_percent_plus_one_zero_votes(self):
        assert check_50_percent_plus_one(0, 0) is False

    def test_50_percent_plus_one_unanimous(self):
        assert check_50_percent_plus_one(1, 1) is True


class TestRateLimiter:
    def test_rate_limiter_allows_first_request(self):
        from rate_limiter import RateLimiter

        rl = RateLimiter(max_attempts=3, window_seconds=60)
        assert rl.is_allowed('test_user') is True

    def test_rate_limiter_blocks_excess(self):
        from rate_limiter import RateLimiter

        rl = RateLimiter(max_attempts=3, window_seconds=60)
        for _ in range(3):
            rl.is_allowed('test_user')
        assert rl.is_allowed('test_user') is False

    def test_rate_limiter_remaining_attempts(self):
        from rate_limiter import RateLimiter

        rl = RateLimiter(max_attempts=5, window_seconds=60)
        for _ in range(3):
            rl.is_allowed('test_user')
        assert rl.remaining_attempts('test_user') == 2

    def test_rate_limiter_separate_keys(self):
        from rate_limiter import RateLimiter

        rl = RateLimiter(max_attempts=3, window_seconds=60)
        for _ in range(3):
            rl.is_allowed('user_a')
        assert rl.is_allowed('user_b') is True


class TestHmacUtils:
    def test_compute_and_verify_hmac(self):
        from hmac_utils import compute_vote_hmac, verify_vote_hmac

        h = compute_vote_hmac('VOTER1', 1, 1, '2024-01-01T00:00:00')
        assert verify_vote_hmac('VOTER1', 1, 1, '2024-01-01T00:00:00', h) is True

    def test_hmac_tamper_detection(self):
        from hmac_utils import compute_vote_hmac, verify_vote_hmac

        h = compute_vote_hmac('VOTER1', 1, 1, '2024-01-01T00:00:00')
        assert verify_vote_hmac('VOTER1', 2, 1, '2024-01-01T00:00:00', h) is False

    def test_hmac_different_timestamp(self):
        from hmac_utils import compute_vote_hmac, verify_vote_hmac

        h = compute_vote_hmac('VOTER1', 1, 1, '2024-01-01T00:00:00')
        assert verify_vote_hmac('VOTER1', 1, 1, '2024-01-02T00:00:00', h) is False

    def test_generate_ballot_paper_id(self):
        from hmac_utils import generate_ballot_paper_id

        bid = generate_ballot_paper_id()
        assert bid.startswith('BALLOT-')
        assert len(bid) == 19
