import os
from datetime import datetime
import pytz
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

IST = pytz.timezone('Asia/Kolkata')
MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME', 'discord_activity')

# Global DB Client (initialized lazily or at module level)
client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
users_col = db['users']
logs_col = db['daily_logs']

def get_ist_time():
    return datetime.now(IST)

async def get_user(user_id):
    """
    Fetch user data from MongoDB. 
    Returns dict or None.
    """
    user_id = str(user_id)
    return await users_col.find_one({"_id": user_id})

async def update_user(user_id, update_func):
    """
    Atomic-ish update based on function logic.
    Since we can't easily pass a func to MongoDB, we fetch, apply, and replace.
    For high concurrency this is not ideal, but sufficient for this bot.
    """
    user_id = str(user_id)
    doc = await users_col.find_one({"_id": user_id})
    
    if not doc:
        doc = {
            "_id": user_id,
            "bhai_count": 0,
            "status": "Active",
            "status_reason": "",
            "attendance": [] # List of {date, marked_at, type (present/halfday)}
        }
    
    update_func(doc)
    
    # Save back
    await users_col.replace_one({"_id": user_id}, doc, upsert=True)
    return doc
