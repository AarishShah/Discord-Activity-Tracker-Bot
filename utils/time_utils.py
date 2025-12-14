from datetime import datetime
from config.settings import IST

def get_ist_time():
    """Returns the current time in IST"""
    return datetime.now(IST)
