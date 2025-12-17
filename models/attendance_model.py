from database.connection import Database
from datetime import datetime

class AttendanceModel:
    @staticmethod
    def get_collection():
        return Database.get_db()['daily_logs']

    @classmethod
    async def find_by_date(cls, user_id, guild_id, date_str):
        return await cls.get_collection().find_one({
            "user_id": user_id,
            "guild_id": guild_id,
            "date": date_str
        })

    @classmethod
    async def create_or_update(cls, user_id, guild_id, date_str, update_data):
        await cls.get_collection().update_one(
            {
                "user_id": user_id,
                "guild_id": guild_id,
                "date": date_str
            },
            update_data,
            upsert=True
        )

    @classmethod
    async def push_command(cls, user_id, guild_id, date_str, command_cmd):
        await cls.get_collection().update_one(
            {
                "user_id": user_id,
                "guild_id": guild_id,
                "date": date_str
            },
            {"$push": {"commands_used": command_cmd}},
            upsert=True # Just in case, broadly safe
        )

    @classmethod
    async def update_command(cls, log_id, command_name, update_fields):
        """
        Updates a specific command entry within a log document.
        Uses array filters logic or explicit positional operator $ if careful.
        For simplicity matching by log_id and command name (assumes unique active or latest).
        Ideally passing specific index or unique ID for command is better, 
        but matching logic from original code: 'commands_used.command': 'present'
        """
        await cls.get_collection().update_one(
            {
                "_id": log_id,
                "commands_used.command": command_name
            },
            {"$set": update_fields}
        )
        
    @classmethod
    async def update_command_by_index(cls, log_id, index, update_fields):
        # Construct update dict dynamically
        update_query = {}
        for key, value in update_fields.items():
            update_query[f"commands_used.{index}.{key}"] = value
            
        await cls.get_collection().update_one(
            {"_id": log_id},
            {"$set": update_query}
        )

    @classmethod
    async def get_logs_in_range(cls, guild_id, start_date, end_date):
        cursor = cls.get_collection().find({
            "guild_id": guild_id,
            "date": {
                "$gte": start_date,
                "$lte": end_date
            }
        })
        return await cursor.to_list(length=None)
