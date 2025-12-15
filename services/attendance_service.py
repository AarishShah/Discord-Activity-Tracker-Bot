from datetime import datetime
from models.attendance_model import AttendanceModel
from services.voice_service import VoiceService
from utils.time_utils import get_ist_time

class AttendanceService:
    
    @classmethod
    async def mark_attendance(cls, user_id, user_name, guild_id, status_value, date_str=None):
        now = get_ist_time()
        today_date = now.date()
        
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return {"success": False, "message": "Invalid date. Use YYYY-MM-DD"}
            
            if target_date < today_date:
                return {"success": False, "message": "You cannot update attendance for past dates."}
            
            target_date_str = date_str
        else:
            target_date_str = now.strftime('%Y-%m-%d')
        
        # Prepare Command Entry
        command_entry = {
            "timestamp": now.isoformat()
        }
        
        status_name = "Present"
        if status_value == "Present":
            command_entry["command"] = "present"
        else:
            command_entry["command"] = "halfday"
            command_entry["type"] = status_value
            status_name = "Half Day"

        # Update DB
        await AttendanceModel.create_or_update(
            user_id, guild_id, target_date_str,
            {
                "$set": {
                    "attendance_status": status_value,
                    "user_name": user_name
                },
                "$push": {"commands_used": command_entry}
            }
        )
        
        message_date = f" for {target_date_str}" if date_str else ""
        return {"success": True, "message": f"You have been marked **{status_name}**{message_date}."}

    @classmethod
    async def start_lunch(cls, user_id, guild_id):
        now = get_ist_time()
        today_str = now.strftime('%Y-%m-%d')
        
        # Check if Present
        existing = await AttendanceModel.find_by_date(user_id, guild_id, today_str)
        if not existing or existing.get('attendance_status') not in ['Present', 'joining_mid_day', 'leaving_mid_day']:
             return {"success": False, "message": "You must mark **Attendance** first."}
             
        await AttendanceModel.push_command(user_id, guild_id, today_str, {
            "command": "lunch",
            "timestamp": now.isoformat()
        })
        return {"success": True, "message": "Enjoy your meal! Status set to **Lunch**. Use `/resume` to resume."}

    @classmethod
    async def set_away(cls, user_id, guild_id, reason="AFK"):
        now = get_ist_time()
        today_str = now.strftime('%Y-%m-%d')
        
        # Check if Present
        existing = await AttendanceModel.find_by_date(user_id, guild_id, today_str)
        if not existing or existing.get('attendance_status') not in ['Present', 'joining_mid_day', 'leaving_mid_day']:
             return {"success": False, "message": "You must mark **Attendance** first."}
             
        await AttendanceModel.push_command(user_id, guild_id, today_str, {
            "command": "away",
            "reason": reason,
            "timestamp": now.isoformat()
        })
        return {"success": True, "message": f"Status set to **Away**: {reason}. Use `/resume` to resume."}

    @classmethod
    async def resume_work(cls, user_id, guild_id):
        now = get_ist_time()
        today_str = now.strftime('%Y-%m-%d')
        
        doc = await AttendanceModel.find_by_date(user_id, guild_id, today_str)
        if not doc:
            return {"success": False, "message": "No attendance record found for today."}
            
        # Find last open status (lunch or away)
        commands = doc.get('commands_used', [])
        target_idx = -1
        target_cmd = None
        
        for i, cmd in enumerate(commands):
            if cmd.get('command') in ['lunch', 'away'] and 'end_time' not in cmd:
                target_idx = i
                target_cmd = cmd
                # Keep searching for the LATEST one? Usually just one open.
                # But let's take the last one found.
        
        if target_idx == -1:
            return {"success": False, "message": "You are not currently away or on lunch."}
            
        # Calculate duration
        start_time = datetime.fromisoformat(target_cmd['timestamp'])
        duration = (now - start_time).total_seconds()
        
        # Close the open status
        await AttendanceModel.update_command_by_index(doc['_id'], target_idx, {
            "end_time": now.isoformat(),
            "duration": round(duration, 2)
        })
        
        # Push resume
        await AttendanceModel.push_command(user_id, guild_id, today_str, {
            "command": "resume",
            "timestamp": now.isoformat()
        })
        
        return {"success": True, "message": "Welcome back! Status set to **Active**."}

    @classmethod
    async def drop_day(cls, user, guild_id):
        now = get_ist_time()
        today_str = now.strftime('%Y-%m-%d')
        
        doc = await AttendanceModel.find_by_date(user.id, guild_id, today_str)
        if not doc:
            return {"success": False, "message": "No attendance record found for today."}

        commands = doc.get('commands_used', [])
        present_cmd = next((c for c in commands if c.get('command') in ['present', 'halfday']), None)
        
        if not present_cmd:
             return {"success": False, "message": "You haven't marked **Attendance** today."}
        
        if 'end_time' in present_cmd:
             return {"success": False, "message": f"You have already dropped for today (Guild: {guild_id})."}

        # Calculate Duration
        start_time = datetime.fromisoformat(present_cmd['timestamp'])
        duration = (now - start_time).total_seconds()
        
        # Update Present/Halfday
        await AttendanceModel.update_command(doc['_id'], present_cmd['command'], {
            "commands_used.$.end_time": now.isoformat(),
            "commands_used.$.duration": round(duration, 2)
        })
        
        # Push drop
        await AttendanceModel.push_command(user.id, guild_id, today_str, {
            "command": "drop",
            "timestamp": now.isoformat()
        })
        
        # Trigger Voice Auto-Disconnect
        await VoiceService.trigger_auto_disconnect(user, guild_id)
        
        return {"success": True, "message": f"Good bye! Day ended. Duration: {round(duration/3600, 2)}h"}

    @classmethod
    async def mark_absent(cls, user_id, user_name, guild_id, date_str, reason):
        now = get_ist_time()
        today_date = now.date()
        
        # Validate Date
        try:
             target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
             return {"success": False, "message": "Invalid date. Use YYYY-MM-DD"}
             
        if target_date < today_date:
             return {"success": False, "message": "You cannot mark attendance for past dates."}

        # Check existing
        existing = await AttendanceModel.find_by_date(user_id, guild_id, date_str)
        if existing and existing.get('attendance_status') in ['Present', 'Absent', 'joining_mid_day', 'leaving_mid_day']:
             return {"success": False, "message": f"Status already set to **{existing.get('attendance_status')}** for {date_str}."}

        await AttendanceModel.create_or_update(
            user_id, guild_id, date_str,
            {
                "$set": {
                    "attendance_status": "Absent",
                    "user_name": user_name,
                    "reason": reason
                },
                "$push": {
                    "commands_used": {
                        "command": "absent",
                        "reason": reason,
                        "timestamp": now.isoformat()
                    }
                }
            }
        )
        return {"success": True, "message": f"Marked as **Absent** on {date_str}: {reason}"}
