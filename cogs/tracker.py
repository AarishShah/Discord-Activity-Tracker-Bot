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

async def setup(bot):
    await bot.add_cog(Tracker(bot))
