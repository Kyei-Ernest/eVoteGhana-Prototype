import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from unittest.mock import patch

import age_calc
from age_calc import age

# Fixed "today" so tests don't break as the real date moves on.
FROZEN_NOW = datetime(2026, 8, 16, 12, 0, 0)


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN_NOW


@patch.object(age_calc, 'datetime', FrozenDateTime)
class TestAgeCalc:
    def test_age_exact_birthday(self):
        birth = datetime(2000, 7, 26)
        assert age(birth) == 26

    def test_age_almost_birthday(self):
        birth = datetime(2001, 7, 27)
        assert age(birth) == 25

    def test_age_just_turned(self):
        birth = datetime(2008, 7, 25)
        assert age(birth) == 18

    def test_age_future_date(self):
        birth = datetime(2027, 7, 26)
        assert age(birth) == -1
