from datetime import datetime


def age(birthdate: datetime) -> int:
    now = datetime.now()
    return now.year - birthdate.year - ((now.month, now.day) < (birthdate.month, birthdate.day))
