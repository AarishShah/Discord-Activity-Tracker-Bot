from datetime import datetime
from config.settings import IST

def get_ist_time():
    """Returns the current time in IST"""
    return datetime.now(IST)

def is_weekend(dt):
    """
    Checks if a given datetime or date is a weekend.
    Weekend is Friday (4) and Saturday (5).
    """
    return dt.weekday() in (4, 5)
