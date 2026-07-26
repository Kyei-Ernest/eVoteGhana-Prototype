import math
from datetime import datetime


def age(then):
    """Calculate a person's age in whole years from their date of birth to the current date."""
    now = datetime.now()
    delta = now - then
    ages = delta.days / 365
    return math.floor(ages)
