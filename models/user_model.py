from database.connection import Database

class UserModel:
    @staticmethod
    def get_collection():
        return Database.get_db()['users']

    @classmethod
    async def get_user(cls, user_id):
        return await cls.get_collection().find_one({"_id": str(user_id)})

    @classmethod
    async def upsert_user(cls, user_doc):
        await cls.get_collection().replace_one(
            {"_id": user_doc["_id"]}, 
            user_doc, 
            upsert=True
        )
