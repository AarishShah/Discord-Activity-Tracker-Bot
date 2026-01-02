from models.attendance_model import AttendanceModel
from models.voice_model import VoiceModel
from models.user_model import UserModel

class MaintenanceService:
    
    @staticmethod
    async def sync_global_stats():
        users_col = UserModel.get_collection()
        
        # 1. Aggregate Bhai Counts from Attendance Logs
        # We need to access the collection directly
        logs_col = AttendanceModel.get_collection()
        
        bhai_pipeline = [
            {
                "$group": {
                    "_id": "$user_id",
                    "total_bhai": {"$sum": "$bhai_count"}
                }
            }
        ]
        
        bhai_cursor = logs_col.aggregate(bhai_pipeline)
        
        count_updates = 0
        async for doc in bhai_cursor:
            user_id = doc["_id"]
            total = doc["total_bhai"]
            
            # Update User
            await users_col.update_one(
                {"_id": str(user_id)},
                {"$set": {"global_bhai_count": total}},
                upsert=True
            )
            count_updates += 1
            
        print(f"[Maintenance] Synced Bhai Counts for {count_updates} users.")
        
        # 2. Aggregate Voice Stats from Daily Activity
        # Note: In VoiceModel schema, 'total_duration' seems to act as 'Regular Duration' 
        # based on the exclusive if/else in append_session.
        activity_col = VoiceModel.get_collection()
        
        voice_pipeline = [
            {
                "$group": {
                    "_id": "$user_id",
                    "total_regular": {"$sum": "$total_duration"},
                    "total_overtime": {"$sum": "$overtime_duration"}
                }
            }
        ]
        
        voice_cursor = activity_col.aggregate(voice_pipeline)
        
        voice_updates = 0
        async for doc in voice_cursor:
            user_id = doc["_id"]
            reg = doc["total_regular"]
            ot = doc["total_overtime"]
            
            await users_col.update_one(
                {"_id": str(user_id)},
                {"$set": {
                    "total_regular_seconds": reg,
                    "total_overtime_seconds": ot
                }},
                upsert=True
            )
            voice_updates += 1
            
        print(f"[Maintenance] Synced Voice Stats for {voice_updates} users.")
        
        return {
            "bhai_updates": count_updates,
            "voice_updates": voice_updates
        }
