import discord
from discord.ext import commands
import json
import os
from datetime import datetime, timezone

SESSION_FILE = 'data/sessions.json'

class Tracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {} # {member_id: {start_time, channel_id, ...}}
        self.sessions_history = []
        self.load_sessions()

    def load_sessions(self):
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, 'r') as f:
                    self.sessions_history = json.load(f)
            except (json.JSONDecodeError, ValueError):
                self.sessions_history = []
        else:
            self.sessions_history = []

    def save_sessions(self):
        # Ensure directory exists just in case
        os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
        with open(SESSION_FILE, 'w') as f:
            json.dump(self.sessions_history, f, indent=4, default=str)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # User joined a voice channel (from None)
        if before.channel is None and after.channel is not None:
            self.active_sessions[member.id] = {
                'start_time': datetime.now(timezone.utc),
                'channel_id': after.channel.id,
                'channel_name': after.channel.name,
                'user_name': member.name
            }
            print(f"[Tracker] Session STARTED: {member.name} in {after.channel.name}")

        # User left a voice channel (to None)
        elif before.channel is not None and after.channel is None:
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
                
                self.sessions_history.append(record)
                self.save_sessions()
                print(f"[Tracker] Session ENDED: {member.name}. Duration: {round(duration, 2)}s")
        
        # NOTE: Switching channels is currently treated as one continuous session 
        # because before.channel IS NOT None and after.channel IS NOT None.
        # The 'channel_name' in the record will receive the name of the INITIAL channel.

    @commands.command()
    async def stats(self, ctx):
        """Shows basic tracking stats."""
        active_count = len(self.active_sessions)
        history_count = len(self.sessions_history)
        await ctx.send(f"📊 **Tracking Stats**\nActive Voice Sessions: {active_count}\nTotal Historical Sessions: {history_count}")

async def setup(bot):
    await bot.add_cog(Tracker(bot))
