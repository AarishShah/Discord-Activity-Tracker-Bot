from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import MONGO_URI, DB_NAME

class Database:
    client: AsyncIOMotorClient = None
    db = None

    @classmethod
    def connect(cls):
        if cls.client is None:
            cls.client = AsyncIOMotorClient(MONGO_URI)
            cls.db = cls.client[DB_NAME]
            print("Connected to MongoDB")

    @classmethod
    def get_db(cls):
        return cls.db

    @classmethod
    def close(cls):
        if cls.client:
            cls.client.close()
            cls.client = None
            print("Closed MongoDB connection")

# Initialize immediately for now, or lazily in app startup
Database.connect()
db = Database.db
