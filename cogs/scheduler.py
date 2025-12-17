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

# Auto Absent: 23:30 IST (18:00 UTC)
TIME_AUTO_ABSENT = time(hour=18, minute=0)
# Daily Export: 00:30 IST (19:00 UTC)
TIME_DAILY_EXPORT = time(hour=19, minute=0)

class Scheduler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auto_absent_task.start()
        self.daily_export_task.start()

    def cog_unload(self):
        self.auto_absent_task.cancel()
        self.daily_export_task.cancel()

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
        month_name = yesterday.strftime('%B')
        
        for guild in self.bot.guilds:
            # Filter Guild
            if target_guild_id and str(guild.id) != str(target_guild_id):
                continue

            try:
                print(f"[Scheduler] Exporting data for {guild.name} ({yesterday_str})...")
                rows = await ExportService.fetch_activity_data(guild, yesterday_str, yesterday_str)
                result = await GoogleSheetsService.append_daily_stats(rows, month_name)
                
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

async def setup(bot):
    await bot.add_cog(Scheduler(bot))
