import asyncio
import discord
from discord import app_commands
from services.voice_service import VoiceService
from services.attendance_service import AttendanceService
from models.attendance_model import AttendanceModel
from models.voice_model import VoiceModel
from models.user_model import UserModel
from utils.time_utils import get_ist_time, is_weekend
from utils.discord_utils import get_attendance_channel
from views.attendance_prompt_view import AttendancePromptView
from services.stats_service import StatsService
from datetime import datetime, timedelta, timezone

class TrackerController:
    # Track pending 1-minute reminder tasks: {member_id: asyncio.Task}
    pending_reminders: dict[int, asyncio.Task] = {}
    # Track users prompted today: {(guild_id, user_id, date_str)}
    prompted_users: set[tuple[int, int, str]] = set()

    @classmethod
    def schedule_reminder(cls, member: discord.Member, channel: discord.VoiceChannel):
        now = get_ist_time()
        # Skip weekends (Friday & Saturday)
        if is_weekend(now):
            return

        cls.cancel_reminder(member.id)
        cls.pending_reminders[member.id] = asyncio.create_task(
            cls._wait_and_prompt(member, channel.guild)
        )

    @classmethod
    def cancel_reminder(cls, member_id: int):
        task = cls.pending_reminders.pop(member_id, None)
        if task and not task.done():
            task.cancel()

    @classmethod
    async def _wait_and_prompt(cls, member: discord.Member, guild: discord.Guild):
        try:
            # Wait for 1 minute (60 seconds)
            await asyncio.sleep(60)

            now = get_ist_time()
            today_str = now.strftime('%Y-%m-%d')

            # 1. Verify user is still in a voice channel in this guild
            if not member.voice or not member.voice.channel or member.voice.channel.guild.id != guild.id:
                return

            # 2. Check if user already marked attendance for today
            has_marked = await AttendanceService.has_marked_attendance_today(member.id, guild.id, now)
            if has_marked:
                return

            # 3. Check if user was already prompted today
            prompt_key = (guild.id, member.id, today_str)
            if prompt_key in cls.prompted_users:
                return

            # 4. Resolve designated attendance channel
            channel = get_attendance_channel(guild)
            if not channel:
                print(f"[Tracker] Attendance channel not found for guild {guild.name}")
                return

            cls.prompted_users.add(prompt_key)
            is_late = AttendanceService.is_past_late_cutoff(now)

            view = AttendancePromptView(target_member=member, is_late=is_late)
            prompt_msg = (
                f"👋 {member.mention}, you have been active in voice for over a minute but haven't marked your attendance today!\n"
                f"Please log your attendance status below:"
            )

            sent_message = await channel.send(content=prompt_msg, view=view)
            view.message = sent_message
            print(f"[Tracker] Sent attendance reminder prompt for {member.display_name} in #{channel.name}")

        except asyncio.CancelledError:
            # Cancelled because user left voice before 1 minute
            pass
        except Exception as e:
            print(f"[Tracker] Error in attendance reminder task for {member.display_name}: {e}")

    @staticmethod
    async def on_voice_state_update(member, before, after):
        # JOIN
        if before.channel is None and after.channel is not None:
            await VoiceService.start_session(member, after.channel)
            TrackerController.schedule_reminder(member, after.channel)
        # LEAVE
        elif before.channel is not None and after.channel is None:
            await VoiceService.end_session(member, before.channel, reason="left")
            TrackerController.cancel_reminder(member.id)
        # SWITCH
        elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
            await VoiceService.end_session(member, before.channel, reason="hopped", silent=False)
            await VoiceService.start_session(member, after.channel, silent=False)
            print(f"[Tracker] {member.display_name} hopped from {before.channel.name} to {after.channel.name}")

    @staticmethod
    async def build_daily_stats_embed(user, guild):
        target = user
        now = get_ist_time()
        today_str = now.strftime('%Y-%m-%d')
        
        # 1. Fetch Attendance
        attendance_log = await AttendanceModel.find_by_date(target.id, guild.id, today_str)
        att_status = "Not Marked"
        if attendance_log:
             s = attendance_log.get('attendance_status', 'Unknown')
             r = attendance_log.get('reason', '')
             att_status = f"{s}" + (f" ({r})" if r else "")

        # 2. Fetch Voice Stats
        today_date = now.date()
        voice_data = await VoiceModel.get_stats(target.id, guild.id, today_str, today_str)
        
        total_voice_sec = 0
        total_overtime_sec = 0
        
        if voice_data:
            doc = voice_data[0]
            total_voice_sec = doc.get('total_duration', 0)
            total_overtime_sec = doc.get('overtime_duration', 0)
            
            # Add Live Session Duration
            if target.id in VoiceService.active_sessions:
                session = VoiceService.active_sessions[target.id]
                if session['guild_id'] == guild.id:
                    start_time = session['start_time'] 
                    current_time = datetime.now(timezone.utc)
                    live_duration = (current_time - start_time).total_seconds()
                    
                    if session['is_overtime']:
                        total_overtime_sec += live_duration
                    else:
                        total_voice_sec += live_duration

        # 3. Bhai Count (Global)
        from services.general_service import GeneralService
        # get_bhai_count now returns global count
        global_count = await GeneralService.get_bhai_count(target, guild.id)
        # get rank
        rank = await GeneralService.get_bhai_rank(target)
        
        # Format Rank: #1, #2, etc.
        rank_str = f"#{rank}" if rank > 0 else "Unranked"
        
        # 4. Format
        voice_str = VoiceService.format_duration(total_voice_sec)
        overtime_str = VoiceService.format_duration(total_overtime_sec)
        
        embed = discord.Embed(title=f"📊 Daily Stats for {target.display_name}", description=f"**{today_str}**", color=discord.Color.blue())
        if target.avatar:
             embed.set_thumbnail(url=target.avatar.url)
        elif target.display_avatar:
             embed.set_thumbnail(url=target.display_avatar.url)
        
        embed.add_field(name="📅 Attendance", value=att_status, inline=False)
        embed.add_field(name="🎙️ Voice Time", value=f"{voice_str}", inline=False)
        embed.add_field(name="⏳ Overtime", value=f"{overtime_str}", inline=False)
        embed.add_field(name="🧔 Bhai Count (Global)", value=f"{global_count} (Rank: {rank_str})", inline=False)
        return embed

    @staticmethod
    async def get_stats(interaction: discord.Interaction, user: discord.Member = None, preset: str = None, start_date: str = None, end_date: str = None):
        try:
            await interaction.response.defer(ephemeral=False)
            target = user or interaction.user
            guild = interaction.guild

            # 1. Resolve Date Range
            start_str, end_str, label, error = StatsService.resolve_date_range(preset, start_date, end_date)
            if error:
                await interaction.followup.send(error, ephemeral=False)
                return

            # 2. Fetch User Stats
            stats = await StatsService.fetch_user_monthly_stats(guild.id, target.id, start_str, end_str)

            # 3. Add Live Session Duration if current day is included in range
            now = get_ist_time()
            today_str = now.strftime('%Y-%m-%d')
            if start_str <= today_str <= end_str and target.id in VoiceService.active_sessions:
                session = VoiceService.active_sessions[target.id]
                if session['guild_id'] == guild.id:
                    start_time = session['start_time']
                    current_time = datetime.now(timezone.utc)
                    live_duration = (current_time - start_time).total_seconds()
                    if session['is_overtime']:
                        stats['overtime_seconds'] += live_duration
                        stats['overtime_formatted'] = StatsService.format_dynamic_duration(stats['overtime_seconds'])
                    else:
                        stats['regular_seconds'] += live_duration
                        stats['regular_formatted'] = StatsService.format_dynamic_duration(stats['regular_seconds'])

            # 4. Build and Send Embed
            embed = StatsService.build_stats_embed(target, guild, label, stats)
            await interaction.followup.send(embed=embed, ephemeral=False)

        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error fetching stats: {str(e)}", ephemeral=False)


