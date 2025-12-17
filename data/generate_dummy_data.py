import json
import random
from datetime import datetime, timedelta

GUILD_ID = 1430929869860245649
USERS = [
    {"id": 1001, "name": "Alice"},
    {"id": 1002, "name": "Bob"},
    {"id": 1003, "name": "Charlie"}
]
START_DATE = datetime(2025, 12, 10)
DAYS_COUNT = 5

daily_activity_data = []
daily_logs_data = []

channels = ["General", "Dev", "Gaming", "Music"]

for i in range(DAYS_COUNT):
    current_date = START_DATE + timedelta(days=i)
    date_str = current_date.strftime("%Y-%m-%d")
    
    # Base start time: 10:00 AM IST approx
    base_time = current_date.replace(hour=10, minute=0, second=0)

    for user in USERS:
        # --- Daily Logs (Attendance) ---
        # Shift timings
        start_offset = random.randint(0, 120) # 0-2 hours late
        work_duration_hours = random.randint(4, 9)
        
        start_dt = base_time + timedelta(minutes=start_offset)
        end_dt = start_dt + timedelta(hours=work_duration_hours)
        
        # Lunch logic (randomly happen)
        has_lunch = random.choice([True, False])
        lunch_start = start_dt + timedelta(hours=4) if has_lunch else None
        lunch_duration = random.randint(30, 60) if has_lunch else 0
        lunch_end = lunch_start + timedelta(minutes=lunch_duration) if has_lunch else None
        
        commands = []
        
        # Present
        present_cmd = {
            "timestamp": start_dt.isoformat() + "+05:30",
            "command": "present",
            "end_time": end_dt.isoformat() + "+05:30",
            "duration": round((end_dt - start_dt).total_seconds(), 2)
        }
        commands.append(present_cmd)
        
        if has_lunch:
            lunch_cmd = {
                "command": "lunch",
                "timestamp": lunch_start.isoformat() + "+05:30",
                "duration": round(lunch_duration * 60, 2),
                "end_time": lunch_end.isoformat() + "+05:30"
            }
            resume_cmd = {
                "command": "resume",
                "timestamp": lunch_end.isoformat() + "+05:30"
            }
            commands.append(lunch_cmd)
            commands.append(resume_cmd)
            
        # Drop
        drop_cmd = {
            "command": "drop",
            "timestamp": end_dt.isoformat() + "+05:30"
        }
        commands.append(drop_cmd)
        
        log_entry = {
            "date": date_str,
            "guild_id": GUILD_ID,
            "user_id": user["id"],
            "attendance_status": "Present",
            "commands_used": commands,
            "user_name": user["name"]
        }
        daily_logs_data.append(log_entry)
        
        # --- Daily Activity (Voice) ---
        # Simulate Sessions roughly matching attendance
        # 1-3 sessions
        sessions = []
        total_voice_duration = 0
        overtime_duration = 0
        
        curr_voice_time = start_dt
        
        while curr_voice_time < end_dt:
            # Session length
            s_len_mins = random.randint(30, 120)
            s_end = curr_voice_time + timedelta(minutes=s_len_mins)
            
            if s_end > end_dt:
                s_end = end_dt # Clip to drop time for regular
            
            duration = (s_end - curr_voice_time).total_seconds()
            
            session = {
                "channel_name": random.choice(channels),
                "start_time": curr_voice_time.isoformat() + "+00:00", # Using UTC format sim
                "end_time": s_end.isoformat() + "+00:00",
                "duration": round(duration, 2),
                "disconnect": random.choice(["left", "hopped", "auto-disconnect"]),
                "status": "regular"
            }
            sessions.append(session)
            total_voice_duration += duration
            
            # Gap between sessions
            curr_voice_time = s_end + timedelta(minutes=random.randint(5, 30))
            
        # Add Overtime Session (Randomly)
        if random.random() > 0.5:
            ot_start = end_dt + timedelta(minutes=5)
            ot_end = ot_start + timedelta(minutes=random.randint(10, 60))
            ot_dur = (ot_end - ot_start).total_seconds()
            
            ot_session = {
                "channel_name": "Gaming",
                "start_time": ot_start.isoformat() + "+00:00",
                "end_time": ot_end.isoformat() + "+00:00",
                "duration": round(ot_dur, 2),
                "disconnect": "left",
                "status": "overtime"
            }
            sessions.append(ot_session)
            overtime_duration += ot_dur
            
        activity_entry = {
            "date": date_str,
            "guild_id": GUILD_ID,
            "user_id": user["id"],
            "sessions": sessions,
            "total_duration": round(total_voice_duration, 2),
            "user_name": user["name"],
            "overtime_duration": round(overtime_duration, 2)
        }
        daily_activity_data.append(activity_entry)

# Write to files
with open("dummy_daily_activity.json", "w") as f:
    json.dump(daily_activity_data, f, indent=2)
    
with open("dummy_daily_logs.json", "w") as f:
    json.dump(daily_logs_data, f, indent=2)

print("Data generated successfully.")
