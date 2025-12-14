from database.connection import Database

class VoiceModel:
    @staticmethod
    def get_collection():
        return Database.get_db()['daily_activity']

    @classmethod
    async def get_stats(cls, user_id, guild_id, start_date_str, end_date_str):
        query = {
            "guild_id": guild_id,
            "date": {
                "$gte": start_date_str,
                "$lte": end_date_str
            }
        }
        if user_id:
            query["user_id"] = user_id
            
        cursor = cls.get_collection().find(query)
        return await cursor.to_list(length=None)

    @classmethod
    async def append_session(cls, user_id, guild_id, date_str, user_name, session_data, duration_seconds, is_overtime=False):
        update_fields = {
            "$set": {"user_name": user_name},
            "$push": {"sessions": session_data}
        }
        
        if is_overtime:
             update_fields["$inc"] = {"overtime_duration": duration_seconds}
        else:
             update_fields["$inc"] = {"total_duration": duration_seconds}
             
        await cls.get_collection().update_one(
            {
                "user_id": user_id,
                "guild_id": guild_id,
                "date": date_str
            },
            update_fields,
            upsert=True
        )
