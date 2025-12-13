import json
import os
from datetime import datetime
import pytz

USER_FILE = 'data/users.json'
IST = pytz.timezone('Asia/Kolkata')

def get_ist_time():
    return datetime.now(IST)

def load_data():
    if not os.path.exists(USER_FILE):
        return {}
    try:
        with open(USER_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    os.makedirs(os.path.dirname(USER_FILE), exist_ok=True)
    with open(USER_FILE, 'w') as f:
        json.dump(data, f, indent=4, default=str)

def update_user(user_id, update_func):
    data = load_data()
    user_id = str(user_id)
    if user_id not in data:
        data[user_id] = {
            "bhai_count": 0,
            "status": "Active",
            "status_reason": "",
            "attendance": [] # List of {date, marked_at, type (present/halfday)}
        }
    
    update_func(data[user_id])
    save_data(data)
    return data[user_id]

def get_user(user_id):
    data = load_data()
    return data.get(str(user_id))
