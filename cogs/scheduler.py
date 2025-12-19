import discord
from discord.ext import commands, tasks
from datetime import time
from services.attendance_service import AttendanceService
from models.attendance_model import AttendanceModel
from utils.time_utils import get_ist_time

# Run at 23:30 IST (11:30 PM)
# Note: tasks.loop time is in UTC if no timezone specified.
# 23:30 IST = 18:00 UTC.
from services.export_service import ExportService
from services.google_sheets_service import GoogleSheetsService
from datetime import datetime, timedelta

# Helper to parse Env IST -> UTC time
import os
from datetime import datetime, time, timedelta

def get_scheduler_time(env_key, default_ist):
    ist_str = os.getenv(env_key, default_ist)
    try:
        h, m = map(int, ist_str.split(':'))
        # Convert IST to UTC (-5:30)
        # Create a dummy datetime to handle day wrap
        dt = datetime(2000, 1, 1, h, m)
        utc_dt = dt - timedelta(hours=5, minutes=30)
        return utc_dt.time()
    except Exception as e:
        print(f"[Scheduler] Error parsing {env_key}: {e}. using default.")
        dt = datetime.strptime(default_ist, "%H:%M") 
        utc_dt = dt - timedelta(hours=5, minutes=30)
        return utc_dt.time()

# Auto Absent: 23:30 IST
TIME_AUTO_ABSENT = get_scheduler_time("ATTENDANCE_AUTO_ABSENT_TIME", "23:30")
# Daily Export: 00:30 IST
TIME_DAILY_EXPORT = get_scheduler_time("ATTENDANCE_EXPORT_TIME", "00:30")
# Auto Drop: Default 22:00 IST ? User didn't specify default, but I'll use 22:00
TIME_AUTO_DROP = get_scheduler_time("ATTENDANCE_END_TIME", "09:00")

class Scheduler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auto_absent_task.start()
        self.daily_export_task.start()
        self.auto_drop_task.start()

    def cog_unload(self):
        self.auto_absent_task.cancel()
        self.daily_export_task.cancel()
        self.auto_drop_task.cancel()
    
    @tasks.loop(time=TIME_AUTO_DROP)
    async def auto_drop_task(self):
        now = get_ist_time()
        
        # Skip Weekends
        if now.weekday() >= 5:
            return

        print(f"[Scheduler] Running Auto-Drop for {now.strftime('%Y-%m-%d')}...")
        
        for guild in self.bot.guilds:
            dropped_users = []
            
            for member in guild.members:
                if member.bot: continue
                
                try:
                    # Attempt Auto Drop
                    result = await AttendanceService.auto_drop(member, guild.id)
                    if result['success']:
                        print(f"[Scheduler] {result['message']} (Guild: {guild.name})")
                        dropped_users.append(member.display_name)
                except Exception as e:
                    print(f"[Scheduler] Error auto-dropping {member.display_name}: {e}")
            
            # Send Notification if users were dropped
            if dropped_users:
                user_list_str = ", ".join(dropped_users)
                message = f"🕰️ **Auto-Drop Summary**: The following users were auto-dropped: {user_list_str}"
                
                # Find Channel
                channel_id = os.getenv("ATTENDANCE_CHANNEL_ID")
                channel = None
                
                if channel_id:
                    channel = guild.get_channel(int(channel_id))
                
                if not channel:
                     # Fallback: finding channel by name
                     channel = discord.utils.get(guild.text_channels, name="general")
                if not channel:
                     channel = discord.utils.get(guild.text_channels, name="attendance")
                     
                if channel:
                    try:
                        await channel.send(message)
                    except Exception as e:
                        print(f"[Scheduler] Failed to send log to channel: {e}")
                else:
                    print(f"[Scheduler] No channel found to log auto-drops. (Msg: {message})")

    @tasks.loop(time=TIME_AUTO_ABSENT)
    async def auto_absent_task(self):
        # ... (Existing Logic) ...
        now = get_ist_time()
        
        # Skip Weekends (Sat=5, Sun=6)
        if now.weekday() >= 5:
            print(f"[Scheduler] Skipping Auto-Absent for {now.strftime('%Y-%m-%d')} (Weekend).")
            return
 
        print(f"[Scheduler] Running Auto-Absent for {now.strftime('%Y-%m-%d')}...")
        
        today_str = now.strftime('%Y-%m-%d')
        
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.bot:
                    continue
                
                # Check Attendance
                try:
                    record = await AttendanceModel.find_by_date(member.id, guild.id, today_str)
                    
                    # If NO record exists, mark absent
                    if not record:
                        print(f"[Scheduler] Marking {member.display_name} (ID: {member.id}) as Absent.")
                        await AttendanceService.mark_absent(
                            user_id=member.id,
                            user_name=member.display_name,
                            guild_id=guild.id,
                            date_str=today_str,
                            reason="Auto-Absent (End of Day)"
                        )
                except Exception as e:
                    print(f"[Scheduler] Error processing {member.display_name}: {e}")

    @tasks.loop(time=TIME_DAILY_EXPORT)
    async def daily_export_task(self):
        print("[Scheduler] Running Daily Export Task...")
        import os
        target_guild_id = os.getenv("TARGET_GUILD_ID")
        
        now = get_ist_time()
        yesterday = now - timedelta(days=1)
        yesterday_str = yesterday.strftime('%Y-%m-%d')
        
        for guild in self.bot.guilds:
            # Filter Guild
            if target_guild_id and str(guild.id) != str(target_guild_id):
                continue

            try:
                print(f"[Scheduler] Exporting data for {guild.name} ({yesterday_str})...")
                rows = await ExportService.fetch_activity_data(guild, yesterday_str, yesterday_str)
                result = await GoogleSheetsService.append_daily_stats(rows, yesterday)
                
                if result['success']:
                    print(f"[Scheduler] Export Success: {result['message']}")
                else:
                     print(f"[Scheduler] Export Failed: {result['message']}")
            except Exception as e:
                print(f"[Scheduler] Error exporting for {guild.name}: {e}")

    @auto_absent_task.before_loop
    async def before_auto_absent(self):
        await self.bot.wait_until_ready()

    @daily_export_task.before_loop
    async def before_daily_export(self):
        await self.bot.wait_until_ready()

    @auto_drop_task.before_loop
    async def before_auto_drop(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Scheduler(bot))
