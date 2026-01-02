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

    @classmethod
    async def increment_bhai_count(cls, user_id, display_name):
        await cls.get_collection().update_one(
            {"_id": str(user_id)},
            {
                "$inc": {"global_bhai_count": 1},
                "$set": {"display_name": display_name}
            },
            upsert=True
        )

    @classmethod
    async def increment_voice_time(cls, user_id, user_name, regular_sec=0, overtime_sec=0):
        await cls.get_collection().update_one(
            {"_id": str(user_id)},
            {
                "$inc": {
                    "total_regular_seconds": regular_sec,
                    "total_overtime_seconds": overtime_sec
                },
                "$set": {"display_name": user_name}
            },
            upsert=True
        )

    @classmethod
    async def get_voice_stats(cls, user_id):
        doc = await cls.get_collection().find_one({"_id": str(user_id)})
        if not doc:
            return {"regular": 0, "overtime": 0}
        return {
            "regular": doc.get('total_regular_seconds', 0),
            "overtime": doc.get('total_overtime_seconds', 0)
        }

    @classmethod
    async def get_bhai_count(cls, user_id):
        doc = await cls.get_collection().find_one({"_id": str(user_id)}, {"global_bhai_count": 1})
        return doc.get('global_bhai_count', 0) if doc else 0

    @classmethod
    async def get_top_bhai_users(cls, limit=5):
        cursor = cls.get_collection().find({"global_bhai_count": {"$gt": 0}}, {"display_name": 1, "global_bhai_count": 1})\
                   .sort("global_bhai_count", -1)\
                   .limit(limit)
        return await cursor.to_list(length=limit)

    @classmethod
    async def get_bottom_bhai_users(cls, limit=5):
        # Only users with count > 0 to make it meaningful? Or include 0s?
        # Assuming > 0 for now to avoid listing inactive people as "leaders"
        cursor = cls.get_collection().find({"global_bhai_count": {"$gt": 0}}, {"display_name": 1, "global_bhai_count": 1})\
                   .sort("global_bhai_count", 1)\
                   .limit(limit)
        return await cursor.to_list(length=limit)

    @classmethod
    async def get_all_bhai_users(cls):
        cursor = cls.get_collection().find({"global_bhai_count": {"$gt": 0}}, {"display_name": 1, "global_bhai_count": 1})\
                   .sort("global_bhai_count", -1)
        return await cursor.to_list(length=None)

    @classmethod
    async def get_bhai_rank(cls, user_id):
        user_count = await cls.get_bhai_count(user_id)
        # Count how many have strictly more
        rank = await cls.get_collection().count_documents({"global_bhai_count": {"$gt": user_count}})
        return rank + 1
