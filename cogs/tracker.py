import discord
from discord.ext import commands
import json
import os
from datetime import datetime, timezone, timedelta
from discord import app_commands
import utils

SESSION_FILE = 'data/sessions.json'

class Tracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {} # {member_id: {start_time, channel_id, ...}}
        self.load_sessions()

    def load_sessions(self):
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, 'r') as f:
                    pass
            except (json.JSONDecodeError, ValueError):
                pass
        else:
            os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
            with open(SESSION_FILE, 'w') as f:
                json.dump([], f)

    def append_session(self, record):
        """Append a single record to the JSON file safely."""
        history = []
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, 'r') as f:
                    history = json.load(f)
            except:
                history = []
        
        history.append(record)
        
        with open(SESSION_FILE, 'w') as f:
            json.dump(history, f, indent=4, default=str)

    def start_session(self, member, channel, silent=False):
        self.active_sessions[member.id] = {
            'start_time': datetime.now(timezone.utc),
            'channel_id': channel.id,
            'channel_name': channel.name,
            'user_name': member.display_name
        }
        if not silent:
            print(f"[Tracker] Session STARTED: {member.display_name} in {channel.name}")

    def end_session(self, member, channel, silent=False):
        if member.id in self.active_sessions:
            session = self.active_sessions.pop(member.id)
            
            start_time = session['start_time']
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            record = {
                'user_id': member.id,
                'user_name': session['user_name'],
                'channel_id': session['channel_id'],
                'channel_name': session['channel_name'],
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': round(duration, 2)
            }
            
            self.append_session(record)
            if not silent:
                print(f"[Tracker] Session ENDED: {member.display_name} in {session['channel_name']}. Duration: {round(duration, 2)}s")
            return record
        return None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # JOIN: From None to Channel
        if before.channel is None and after.channel is not None:
            self.start_session(member, after.channel)

        # LEAVE: From Channel to None
        elif before.channel is not None and after.channel is None:
            self.end_session(member, before.channel)

        # SWITCH: From Channel A to Channel B
        elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
            # End previous (silent)
            record = self.end_session(member, before.channel, silent=True)
            # Start new (silent)
            self.start_session(member, after.channel, silent=True)
            
            # Custom Log
            prev_dur = f"{record['duration_seconds']}s" if record else "?"
            print(f"[Tracker] {member.display_name} hopped from {before.channel.name} to {after.channel.name} (Prev: {prev_dur})")

    @commands.command()
    async def stats(self, ctx):
        """Shows active session count."""
        await ctx.send(f"📊 **Tracking Stats**\nActive Voice Sessions: {len(self.active_sessions)}")

    def get_daily_stats(self, user_id, date_str):
        """
        Aggregates session data for a given user on a specific date (IST).
        date_str: 'YYYY-MM-DD'
        """
        user_id = int(user_id)
        sessions = []
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, 'r') as f:
                    sessions = json.load(f)
            except:
                pass

        total_duration = 0
        session_count = 0
        channel_stats = {} # {channel_name: duration}

        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        for s in sessions:
            if s['user_id'] != user_id:
                continue
            
            # Convert UTC start_time to IST to check date
            # Assuming start_time in json is ISO format from datetime.now(timezone.utc)
            try:
                start_dt_utc = datetime.fromisoformat(s['start_time'])
                # Convert to IST
                start_dt_ist = start_dt_utc.astimezone(utils.IST)
                
                if start_dt_ist.date() == target_date:
                    dur = s.get('duration_seconds', 0)
                    total_duration += dur
                    session_count += 1
                    
                    c_name = s.get('channel_name', 'Unknown')
                    channel_stats[c_name] = channel_stats.get(c_name, 0) + dur
            except (ValueError, TypeError):
                continue

        return {
            "total_duration": total_duration,
            "session_count": session_count,
            "channel_stats": channel_stats
        }

    @app_commands.command(name="statistic", description="Get activity stats for a user on a specific date")
    @app_commands.describe(user="The user to view stats for", date="Date (YYYY-MM-DD). Defaults to today.")
    async def statistic(self, interaction: discord.Interaction, user: discord.Member, date: str = None):
        # 1. Determine Date
        if date is None:
            date_obj = utils.get_ist_time().date()
            date_str = date_obj.strftime('%Y-%m-%d')
        else:
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d').date()
                date_str = date
            except ValueError:
                await interaction.response.send_message("❌ Invalid date format. Please use `YYYY-MM-DD`.", ephemeral=True)
                return

        # 2. Get User Info & Attendance
        user_data = utils.get_user(user.id)
        attendance_status = "Not Marked"
        
        if user_data and 'attendance' in user_data:
            for entry in user_data['attendance']:
                if entry['date'] == date_str:
                    attendance_status = entry['type'].title()
                    if entry.get('reason'):
                        attendance_status += f" ({entry['reason']})"
                    break
        
        # 3. Get Voice Stats
        stats = self.get_daily_stats(user.id, date_str)
        
        # 4. Format Duration
        def format_duration(seconds):
            m, s = divmod(int(seconds), 60)
            h, m = divmod(m, 60)
            if h > 0:
                return f"{h}h {m}m"
            return f"{m}m {s}s"

        duration_str = format_duration(stats['total_duration'])
        
        # 5. Build Embed
        embed = discord.Embed(
            title=f"📊 Statistics for {user.display_name}",
            description=f"Activity report for **{date_str}**",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="📅 Attendance", value=attendance_status, inline=True)
        embed.add_field(name="🎙️ Voice Sessions", value=str(stats['session_count']), inline=True)
        embed.add_field(name="⏱️ Total Voice Time", value=duration_str, inline=True)
        
        if stats['channel_stats']:
            channels_desc = ""
            for name, dur in stats['channel_stats'].items():
                channels_desc += f"• **{name}**: {format_duration(dur)}\n"
            embed.add_field(name="🔊 Channel Breakdown", value=channels_desc, inline=False)
        else:
            embed.add_field(name="🔊 Channel Breakdown", value="No voice activity recorded.", inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Tracker(bot))
