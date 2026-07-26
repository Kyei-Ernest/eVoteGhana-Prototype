import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from age_calc import age
from datetime import datetime
import pytest


class TestAgeCalc:
    def test_age_exact_birthday(self):
        from datetime import timedelta
        birth = datetime.now() - timedelta(days=365 * 25)
        result = age(birth)
        assert result == 25

    def test_age_almost_birthday(self):
        from datetime import timedelta
        birth = datetime.now() - timedelta(days=365 * 25 + 364)
        result = age(birth)
        assert result == 25

    def test_age_just_turned(self):
        from datetime import timedelta
        birth = datetime.now() - timedelta(days=365 * 18)
        result = age(birth)
        assert result == 18

    def test_age_future_date(self):
        from datetime import timedelta
        birth = datetime.now() + timedelta(days=365)
        result = age(birth)
        assert result == -1
