import discord
import os
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta
from config.settings import IST
from services.attendance_service import AttendanceService
from services.voice_service import VoiceService
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
# Shift Start: Default 09:00 IST
TIME_SHIFT_START = get_scheduler_time("ATTENDANCE_START_TIME", "09:00")

class Scheduler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auto_absent_task.start()
        self.daily_export_task.start()
        self.auto_drop_task.start()
        self.shift_start_task.start()
        print(f"[Scheduler] Tasks started. Auto-Absent: {TIME_AUTO_ABSENT}, Export: {TIME_DAILY_EXPORT}, Auto-Drop: {TIME_AUTO_DROP}, Shift-Start: {TIME_SHIFT_START}")

    def cog_unload(self):
        self.auto_absent_task.cancel()
        self.daily_export_task.cancel()
        self.auto_drop_task.cancel()
        self.shift_start_task.cancel()
    
    @tasks.loop(time=TIME_AUTO_DROP)
    async def auto_drop_task(self):
        now = get_ist_time()
        
        # Skip Weekends
        if now.weekday() >= 5:
            return

        print(f"[Scheduler] Running Auto-Drop for {now.strftime('%Y-%m-%d')}...")
        
        for guild in self.bot.guilds:
            dropped_users = []
            failed_users = []
            
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
                    failed_users.append(f"{member.display_name} ({str(e)})")
            
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
            
            # Send Notification if failures occurred
            if failed_users:
                error_msg = f"⚠️ **Auto-Drop Failures**: Could not drop the following users:\n" + "\n".join([f"- {u}" for u in failed_users])
                channel = get_log_channel(guild)
                if channel:
                    await channel.send(error_msg)

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
            failed_users = []
            
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
                    failed_users.append(f"{member.display_name} ({str(e)})")
            
            channel = get_log_channel(guild)
            
            # Send Notification
            if absent_users:
                if channel:
                    user_list = ", ".join(absent_users)
                    await channel.send(f"📉 **Auto-Absent Summary**: The following users were marked absent: {user_list}")

            # Send Failure Notification
            if failed_users:
                if channel:
                    error_msg = f"⚠️ **Auto-Absent Failures**: Could not mark the following users:\n" + "\n".join([f"- {u}" for u in failed_users])
                    await channel.send(error_msg)

                if channel:
                    error_msg = f"⚠️ **Auto-Absent Failures**: Could not mark the following users:\n" + "\n".join([f"- {u}" for u in failed_users])
                    await channel.send(error_msg)

    @tasks.loop(time=TIME_SHIFT_START)
    async def shift_start_task(self):
        """
        Runs at the start of the work day (e.g. 9 AM).
        Checks for users who are in 'pre_shift' overtime and switches them to Regular.
        """
        now = get_ist_time()
        print(f"[Scheduler] Running Shift-Start Check for {now.strftime('%Y-%m-%d')}...")
        
        # Skip Weekends
        if now.weekday() >= 5:
            return

        switched_users = []
        
        # Snapshot of keys to avoid modification during iteration
        active_ids = list(VoiceService.active_sessions.keys())
        
        for member_id in active_ids:
            session = VoiceService.active_sessions.get(member_id)
            if not session: continue
            
            if session.get('overtime_reason') == 'pre_shift':
                guild_id = session['guild_id']
                guild = self.bot.get_guild(guild_id)
                if not guild: continue
                
                member = guild.get_member(member_id)
                channel = guild.get_channel(session['channel_id'])
                
                if member and channel:
                    try:
                        # 1. End Overtime Session
                        await VoiceService.end_session(member, channel, reason="shift_start")
                        # 2. Start Regular Session
                        # Since it is now >= 9 AM, start_session will not mark it as pre_shift
                        await VoiceService.start_session(member, channel)
                        
                        switched_users.append(member.display_name)
                        print(f"[Scheduler] Switched {member.display_name} from Pre-Shift OT to Regular.")
                        
                    except Exception as e:
                        print(f"[Scheduler] Error switching session for {member.display_name}: {e}")

        # Notification
        if switched_users:
            # Group by Guild to be polite? Or just send to relevant guild logs.
            # Simplified: finding first guild found in loop? No, iterating global users.
            # Ideally map users to guilds and send batch messages.
            # Since we have guild object inside...
            
            # Simple approach: Log to console mainly, maybe find first guild log.
            # Or iterate set of guilds affected.
            user_list = ", ".join(switched_users)
            print(f"[Scheduler] Shift Start Summary: Switched {len(switched_users)} users: {user_list}")

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

    @shift_start_task.before_loop
    async def before_shift_start(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Scheduler(bot))
