import discord
import os
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta
from config.settings import IST
from services.attendance_service import AttendanceService
from models.attendance_model import AttendanceModel
from utils.time_utils import get_ist_time
from services.export_service import ExportService
from services.google_sheets_service import GoogleSheetsService
from utils.discord_utils import get_log_channel

def get_scheduler_time(env_key, default_ist):
    ist_str = os.getenv(env_key, default_ist).strip('"\'')
    try:
        h, m = map(int, ist_str.split(':'))
        # Return time object with IST timezone
        # discord.ext.tasks will handle the UTC conversion automatically
        return time(hour=h, minute=m, tzinfo=IST)
    except Exception as e:
        print(f"[Scheduler] Error parsing {env_key} ('{ist_str}'): {e}. Using default {default_ist}")
        h, m = map(int, default_ist.split(':'))
        return time(hour=h, minute=m, tzinfo=IST)

# Auto Absent: 23:30 IST
TIME_AUTO_ABSENT = get_scheduler_time("ATTENDANCE_AUTO_ABSENT_TIME", "23:30")
# Daily Export: 00:30 IST
TIME_DAILY_EXPORT = get_scheduler_time("ATTENDANCE_EXPORT_TIME", "00:30")
# Auto Drop: Default 22:00 IST
TIME_AUTO_DROP = get_scheduler_time("ATTENDANCE_END_TIME", "22:00")

class Scheduler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auto_absent_task.start()
        self.daily_export_task.start()
        self.auto_drop_task.start()
        print(f"[Scheduler] Tasks started. Auto-Absent: {TIME_AUTO_ABSENT}, Export: {TIME_DAILY_EXPORT}, Auto-Drop: {TIME_AUTO_DROP}")

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
                channel = get_log_channel(guild)
                     
                if channel:
                    try:
                        await channel.send(message)
                    except Exception as e:
                        print(f"[Scheduler] Failed to send log to channel: {e}")
                else:
                    print(f"[Scheduler] No channel found to log auto-drops. (Msg: {message})")

    @tasks.loop(time=TIME_AUTO_ABSENT)
    async def auto_absent_task(self):
        now = get_ist_time()
        
        # Skip Weekends (Sat=5, Sun=6)
        if now.weekday() >= 5:
            print(f"[Scheduler] Skipping Auto-Absent for {now.strftime('%Y-%m-%d')} (Weekend).")
            return
 
        print(f"[Scheduler] Running Auto-Absent for {now.strftime('%Y-%m-%d')}...")
        today_str = now.strftime('%Y-%m-%d')
        
        for guild in self.bot.guilds:
            absent_users = []
            
            for member in guild.members:
                if member.bot: continue
                
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
                        absent_users.append(member.display_name)
                except Exception as e:
                    print(f"[Scheduler] Error processing {member.display_name}: {e}")
            
            # Send Notification
            if absent_users:
                channel = get_log_channel(guild)
                if channel:
                    user_list = ", ".join(absent_users)
                    await channel.send(f"📉 **Auto-Absent Summary**: The following users were marked absent: {user_list}")

    @tasks.loop(time=TIME_DAILY_EXPORT)
    async def daily_export_task(self):
        print("[Scheduler] Running Daily Export Task...")
        target_guild_id = os.getenv("TARGET_GUILD_ID")
        
        now = get_ist_time()
        yesterday = now - timedelta(days=1)
        yesterday_str = yesterday.strftime('%Y-%m-%d')
        
        for guild in self.bot.guilds:
            print(f"[Scheduler] Checking guild: {guild.name} ({guild.id})")
            # Filter Guild
            if target_guild_id and str(guild.id) != str(target_guild_id):
                continue
            
            channel = get_log_channel(guild)

            try:
                print(f"[Scheduler] Exporting data for {guild.name} ({yesterday_str})...")
                rows = await ExportService.fetch_activity_data(guild, yesterday_str, yesterday_str)
                result = await GoogleSheetsService.append_daily_stats(rows, yesterday)
                
                if result['success']:
                    print(f"[Scheduler] Export Success: {result['message']}")
                    if channel:
                        await channel.send(f"📊 **Daily Export**: Data for **{yesterday_str}** has been successfully updated in Google Sheets.")
                else:
                     print(f"[Scheduler] Export Failed: {result['message']}")
                     if channel:
                        await channel.send(f"⚠️ **Daily Export Failed**: {result['message']}")

            except Exception as e:
                print(f"[Scheduler] Error exporting for {guild.name}: {e}")
                if channel:
                    await channel.send(f"⚠️ **Daily Export Error**: {str(e)}")

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
