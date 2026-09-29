import asyncio
from datetime import datetime, timedelta, timezone
import discord
from config.settings import IST
from models.attendance_model import AttendanceModel
from models.voice_model import VoiceModel
from utils.discord_utils import get_log_channel
from utils.time_utils import get_ist_time

class StatsService:
    @classmethod
    def get_previous_month_range(cls, reference_date=None):
        """
        Calculates the start and end dates of the previous month.
        Returns: (start_date_str, end_date_str, month_name, start_dt, end_dt)
        e.g., ('2026-08-01', '2026-08-31', 'August 2026', ...)
        """
        ref = reference_date or get_ist_time()
        # First day of the current month
        first_of_current = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Last day of the previous month
        last_of_previous = first_of_current - timedelta(days=1)
        # First day of the previous month
        first_of_previous = last_of_previous.replace(day=1)

        start_date_str = first_of_previous.strftime('%Y-%m-%d')
        end_date_str = last_of_previous.strftime('%Y-%m-%d')
        month_name = first_of_previous.strftime('%B %Y')

        return start_date_str, end_date_str, month_name, first_of_previous, last_of_previous

    @classmethod
    def format_dynamic_duration(cls, seconds: float | int) -> str:
        """
        Formats duration into dynamic logical units:
        - >= 24 hours: '1 day (36 hours)', '7 days (170 hours)'
        - 1 to 23 hours: '23 hours', '1 hour'
        - < 1 hour: '45 mins', '1 min', or '0 hours'
        """
        if not seconds or seconds <= 0:
            return "0 hours"

        total_hours = int(seconds // 3600)
        if total_hours >= 24:
            days = total_hours // 24
            day_str = "day" if days == 1 else "days"
            return f"{days} {day_str} ({total_hours} hours)"
        elif total_hours > 0:
            hour_str = "hour" if total_hours == 1 else "hours"
            return f"{total_hours} {hour_str}"
        else:
            total_minutes = int(seconds // 60)
            if total_minutes > 0:
                min_str = "min" if total_minutes == 1 else "mins"
                return f"{total_minutes} {min_str}"
            return "0 hours"

    @classmethod
    def _format_date(cls, date_str: str) -> str:
        """
        Formats 'YYYY-MM-DD' into 'Monday, 21 August 2026'
        """
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        return f"{dt.strftime('%A')}, {dt.day} {dt.strftime('%B %Y')}"

    @classmethod
    async def fetch_user_monthly_stats(cls, guild_id: int, user_id: int, start_date_str: str, end_date_str: str):
        """
        Gathers attendance (absences, half days) and voice activity (regular, overtime)
        for a specific user within a date range.
        """
        # 1. Fetch attendance records
        attendance_logs = await AttendanceModel.get_logs_in_range(
            guild_id, start_date_str, end_date_str, user_id=user_id
        )

        absent_dates = []
        half_day_dates = []
        half_day_statuses = {'joining_mid_day', 'leaving_mid_day', 'Half Day', 'halfday'}

        for log in sorted(attendance_logs, key=lambda x: x.get('date', '')):
            status = log.get('attendance_status')
            raw_date = log.get('date')
            if not raw_date:
                continue

            formatted_date = cls._format_date(raw_date)

            if status == "Absent":
                absent_dates.append(formatted_date)
            elif status in half_day_statuses:
                half_day_dates.append(formatted_date)

        # 2. Fetch voice records
        voice_logs = await VoiceModel.get_stats(user_id, guild_id, start_date_str, end_date_str)
        regular_sec = sum(doc.get('total_duration', 0) for doc in voice_logs)
        overtime_sec = sum(doc.get('overtime_duration', 0) for doc in voice_logs)

        return {
            "absences": absent_dates,
            "half_days": half_day_dates,
            "regular_seconds": regular_sec,
            "overtime_seconds": overtime_sec,
            "regular_formatted": cls.format_dynamic_duration(regular_sec),
            "overtime_formatted": cls.format_dynamic_duration(overtime_sec)
        }

    @classmethod
    def _truncate_field_value(cls, items: list[str], max_len: int = 1000) -> str:
        """
        Formats a list of numbered items and truncates if approaching Discord's 1024-character field limit.
        """
        if not items:
            return "None"

        lines = [f"{i + 1}. {item}" for i, item in enumerate(items)]
        full_text = "\n".join(lines)
        if len(full_text) <= max_len:
            return full_text

        # Truncate gracefully
        truncated_lines = []
        current_len = 0
        for i, line in enumerate(lines):
            remaining_count = len(lines) - i
            overflow_notice = f"\n...and {remaining_count} more"
            if current_len + len(line) + len(overflow_notice) + 1 > max_len:
                truncated_lines.append(f"...and {remaining_count} more")
                break
            truncated_lines.append(line)
            current_len += len(line) + 1

        return "\n".join(truncated_lines)

    @classmethod
    def build_monthly_stats_embed(cls, user, guild, month_name: str, stats_data: dict, generated_at: datetime = None) -> discord.Embed:
        """
        Builds the Discord Embed matching the Task 1 acceptance criteria and JSON format.
        """
        now = generated_at or get_ist_time()
        guild_name = guild.name if hasattr(guild, 'name') else str(guild)

        embed = discord.Embed(
            title=f"Monthly Attendance & Activity Stats | {month_name}",
            description=f"*Hello! Here is your automated attendance and voice activity summary for the previous month in **{guild_name}**.*",
            color=5814783  # 0x58B9FF
        )

        absences = stats_data.get("absences", [])
        half_days = stats_data.get("half_days", [])
        regular_formatted = stats_data.get("regular_formatted", "0 hours")
        overtime_formatted = stats_data.get("overtime_formatted", "0 hours")

        embed.add_field(
            name=f"Absences ({len(absences)})",
            value=cls._truncate_field_value(absences),
            inline=False
        )

        embed.add_field(
            name=f"Half Days ({len(half_days)})",
            value=cls._truncate_field_value(half_days),
            inline=False
        )

        embed.add_field(
            name="Total Voice Time",
            value=regular_formatted,
            inline=True
        )

        embed.add_field(
            name="Voice Overtime",
            value=overtime_formatted,
            inline=True
        )

        # Footer format: 'Generated on 01-Sep-2026 06:00 AM'
        embed.set_footer(text=f"Generated on {now.strftime('%d-%b-%Y %I:%M %p')}")
        embed.timestamp = now

        return embed

    @classmethod
    async def send_monthly_stats_to_guild(cls, bot: discord.Client, guild: discord.Guild, reference_date: datetime = None):
        """
        Aggregates stats for all non-bot members of the guild and delivers embeds via DM.
        Includes rate-limiting and logging.
        """
        start_date_str, end_date_str, month_name, _, _ = cls.get_previous_month_range(reference_date)
        now = reference_date or get_ist_time()

        print(f"[StatsService] Generating monthly stats for {guild.name} ({month_name}: {start_date_str} to {end_date_str})...")

        sent_count = 0
        forbidden_count = 0
        failed_users = []

        for member in guild.members:
            if member.bot:
                continue

            try:
                stats = await cls.fetch_user_monthly_stats(guild.id, member.id, start_date_str, end_date_str)
                embed = cls.build_monthly_stats_embed(member, guild, month_name, stats, generated_at=now)

                await member.send(embed=embed)
                sent_count += 1
                # Small pause to avoid hitting Discord DM rate limits
                await asyncio.sleep(0.5)

            except discord.Forbidden:
                print(f"[StatsService] Could not DM {member.display_name} (DMs disabled / blocked).")
                forbidden_count += 1
            except Exception as e:
                print(f"[StatsService] Failed to send monthly stats to {member.display_name}: {e}")
                failed_users.append((member.display_name, str(e)))

        # Log results to the guild's log channel
        log_channel = get_log_channel(guild)
        if log_channel:
            summary_msg = (
                f"📊 **Monthly Attendance & Voice Stats Summary | {month_name}**\n\n"
                f"> - ✅ Sent DMs to: **{sent_count}** members\n"
                f"> - 🚫 DMs Disabled/Blocked: **{forbidden_count}** members\n"
            )
            if failed_users:
                failure_list = "\n".join([f"> - {name}: {err}" for name, err in failed_users[:10]])
                summary_msg += f"> - ⚠️ Failed Delivery ({len(failed_users)}):\n{failure_list}\n"

            try:
                await log_channel.send(summary_msg)
            except Exception as e:
                print(f"[StatsService] Failed to send summary to log channel: {e}")

        print(f"[StatsService] Completed monthly stats for {guild.name}: {sent_count} sent, {forbidden_count} DMs blocked, {len(failed_users)} failed.")
        return {
            "sent": sent_count,
            "forbidden": forbidden_count,
            "failed": failed_users
        }
