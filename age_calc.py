import math
from datetime import datetime


def age(then):
    now = datetime.now()
    delta = now - then
    ages = delta.days / 365
    return math.floor(ages)


'''then is the date of birth of the individual
and now refers to the current date'''
