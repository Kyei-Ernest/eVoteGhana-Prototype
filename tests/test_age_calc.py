import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from age_calc import age
from datetime import datetime
import pytest


class TestAgeCalc:
    def test_age_exact_birthday(self):
        birth = datetime(2000, 7, 26)
        result = age(birth)
        assert result == 26

    def test_age_almost_birthday(self):
        birth = datetime(2001, 7, 27)
        result = age(birth)
        expected = 24 if birth.month > 7 or (birth.month == 7 and birth.day > 26) else 25
        assert result == 24

    def test_age_just_turned(self):
        birth = datetime(2008, 7, 25)
        result = age(birth)
        assert result == 18

    def test_age_future_date(self):
        birth = datetime(2027, 7, 26)
        result = age(birth)
        assert result == -1
