import discord
from discord.ext import commands

from datetime import datetime, timezone, timedelta
from discord import app_commands
import utils



class Tracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {} # {member_id: {start_time, channel_id, ...}}
        self.daily_col = utils.db['daily_activity']

    async def append_session(self, record):
        """Append session to daily document."""
        # record has: user_id, user_name, channel_name, start_time, end_time, duration_seconds
        
        # Determine Date (IST)
        start_dt = datetime.fromisoformat(record['start_time'])
        ist_date = start_dt.astimezone(utils.IST).date()
        date_str = ist_date.strftime('%Y-%m-%d')
        
        session_detail = {
            "channel_name": record['channel_name'],
            "start_time": record['start_time'],
            "end_time": record['end_time'],
            "duration": record['duration_seconds'],
            "disconnect": record.get('disconnect', 'unknown')
        }
        
        # Update/Upsert
        await self.daily_col.update_one(
            {
                "user_id": record['user_id'],
                "date": date_str
            },
            {
                "$set": {"user_name": record['user_name']}, # Keep name updated
                "$inc": {"total_duration": record['duration_seconds']},
                "$push": {"sessions": session_detail}
            },
            upsert=True
        )

    def start_session(self, member, channel, silent=False):
        self.active_sessions[member.id] = {
            'start_time': datetime.now(timezone.utc),
            'channel_id': channel.id,
            'channel_name': channel.name,
            'user_name': member.display_name
        }
        if not silent:
            print(f"[Tracker] Session STARTED: {member.display_name} in {channel.name}")

    async def end_session(self, member, channel, reason="left", silent=False):
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
                'duration_seconds': round(duration, 2),
                'disconnect': reason
            }
            
            await self.append_session(record)
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
            await self.end_session(member, before.channel, reason="left")

        # SWITCH: From Channel A to Channel B
        elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
            # End previous (silent)
            record = await self.end_session(member, before.channel, reason="hopped", silent=True)
            # Start new (silent)
            self.start_session(member, after.channel, silent=True)
            
            # Custom Log
            prev_dur = f"{record['duration_seconds']}s" if record else "?"
            print(f"[Tracker] {member.display_name} hopped from {before.channel.name} to {after.channel.name} (Prev: {prev_dur})")






    async def get_stats(self, user_id, start_date, end_date):
        """
        Aggregates session data for a given user within a date range (Inclusive).
        dates are datetime.date objects.
        """
        user_id = int(user_id) if user_id else None
        
        # Build Query
        query = {
            "date": {
                "$gte": start_date.strftime('%Y-%m-%d'),
                "$lte": end_date.strftime('%Y-%m-%d')
            }
        }
        if user_id:
            query['user_id'] = user_id
            
        daily_docs = await self.daily_col.find(query).to_list(length=None)

        total_duration = 0
        session_count = 0
        channel_stats = {} # {channel_name: duration}

        for doc in daily_docs:
            total_duration += doc.get('total_duration', 0)
            
            # Aggregate sessions for channel stats and count
            sessions = doc.get('sessions', [])
            session_count += len(sessions)
            
            for s in sessions:
                c_name = s.get('channel_name', 'Unknown')
                dur = s.get('duration', 0)
                channel_stats[c_name] = channel_stats.get(c_name, 0) + dur

        return {
            "total_duration": total_duration,
            "session_count": session_count,
            "channel_stats": channel_stats
        }

    @app_commands.command(name="statistic", description="Get activity stats")
    @app_commands.describe(
        user="Specific user (Optional)", 
        date="Date (YYYY-MM-DD) (Optional)", 
        month="Month (YYYY-MM) (Optional)"
    )
    async def statistic(self, interaction: discord.Interaction, user: discord.Member = None, date: str = None, month: str = None):
        # Determine Period
        start_date = None
        end_date = None
        title_date = ""

        today = utils.get_ist_time().date()
        
        try:
            if month:
                # Month Logic
                d = datetime.strptime(month, '%Y-%m').date()
                start_date = d.replace(day=1)
                # End date is last day of month
                next_month = d.replace(day=28) + timedelta(days=4)
                end_date = next_month - timedelta(days=next_month.day)
                title_date = f"Month: {month}"
            elif date:
                # Specific Date Logic
                d = datetime.strptime(date, '%Y-%m-%d').date()
                start_date = d
                end_date = d
                title_date = date
            else:
                # Default: Today
                start_date = today
                end_date = today
                title_date = str(today)
                
        except ValueError:
             await interaction.response.send_message("❌ Invalid format. Date: YYYY-MM-DD, Month: YYYY-MM", ephemeral=True)
             return

        # Fetch Stats
        target_users = [user] if user else []
        
        # If no user specified, we might need all users. 
        # For now, let's stick to the requested behavior: 
        # "if user is None: Fetch stats for all users"
        # However, listing ALL users in one embed is hard. 
        # Let's do a summary for all users in the server who have data.
        
        if not user:
            # Aggregate for ALL known users
            # Logic: Group by user_id from daily docs in range
            query = {
                "date": {
                    "$gte": start_date.strftime('%Y-%m-%d'),
                    "$lte": end_date.strftime('%Y-%m-%d')
                }
            }
            daily_docs = await self.daily_col.find(query).to_list(length=None)
            
            # {user_id: {total_duration, session_count}}
            user_stats = {}
            user_names = {}
            
            for doc in daily_docs:
                uid = doc['user_id']
                name = doc.get('user_name', str(uid))
                user_names[uid] = name
                
                if uid not in user_stats:
                    user_stats[uid] = {'total_duration': 0, 'session_count': 0}
                
                user_stats[uid]['total_duration'] += doc.get('total_duration', 0)
                sessions = doc.get('sessions', [])
                user_stats[uid]['session_count'] += len(sessions)
            
            if not user_stats:
                await interaction.response.send_message(f"No activity found for **{title_date}**.", ephemeral=True)
                return

            # Prepare list of users
            sorted_users = sorted(user_stats.items(), key=lambda x: user_names.get(x[0], str(x[0]))) # Sort by name
            
            # Chunking (5 users per embed)
            CHUNK_SIZE = 5
            chunks = [sorted_users[i:i + CHUNK_SIZE] for i in range(0, len(sorted_users), CHUNK_SIZE)]
            
            # Send first chunk
            first = True
            for i, chunk in enumerate(chunks):
                embed = discord.Embed(title=f"📊 Global Statistics ({i+1}/{len(chunks)})", description=f"Activity for **{title_date}**", color=discord.Color.gold())
                
                for uid, stats in chunk:
                    name = user_names.get(uid, f"User {uid}")
                    time_str = self.format_duration(stats['total_duration'])
                    count = stats['session_count']
                    embed.add_field(name=f"👤 {name}", value=f"🎙️ **{count}** Sessions\n⏱️ **{time_str}**", inline=False)
                
                if first:
                    await interaction.response.send_message(embed=embed)
                    first = False
                else:
                    await interaction.followup.send(embed=embed)
            return

        # Specific User Stats
        stats = await self.get_stats(user.id, start_date, end_date)
        duration_str = self.format_duration(stats['total_duration'])
        
        embed = discord.Embed(
            title=f"📊 Statistics for {user.display_name}",
            description=f"Activity for **{title_date}**",
            color=discord.Color.blue()
        )
        
        # Attendance only relevant for single date
        if start_date == end_date:
            user_data = await utils.get_user(user.id)
            attendance_status = "Not Marked"
            if user_data and 'attendance' in user_data:
                for entry in user_data['attendance']:
                    if entry['date'] == str(start_date):
                        attendance_status = entry['type'].title() + (f" ({entry['reason']})" if entry.get('reason') else "")
                        break
            embed.add_field(name="📅 Attendance", value=attendance_status, inline=True)

        embed.add_field(name="🎙️ Voice Sessions", value=str(stats['session_count']), inline=True)
        embed.add_field(name="⏱️ Total Voice Time", value=duration_str, inline=True)
        
        if stats['channel_stats']:
            channels_desc = ""
            for name, dur in stats['channel_stats'].items():
                channels_desc += f"• **{name}**: {self.format_duration(dur)}\n"
            embed.add_field(name="🔊 Channel Breakdown", value=channels_desc, inline=False)
        else:
            embed.add_field(name="🔊 Channel Breakdown", value="No voice activity recorded.", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Show top users by voice activity")
    @app_commands.describe(month="Month (YYYY-MM). Default: Current Month", sort="Sort order (default: Descending)")
    @app_commands.choices(sort=[
        app_commands.Choice(name="Descending (Highest First)", value="desc"),
        app_commands.Choice(name="Ascending (Lowest First)", value="asc")
    ])
    async def leaderboard(self, interaction: discord.Interaction, month: str = None, sort: app_commands.Choice[str] = None):
        # Determine Range
        today = utils.get_ist_time().date()
        start_date = today.replace(day=1)
        next_month = (start_date + timedelta(days=32)).replace(day=1)
        end_date = next_month - timedelta(days=1)
        title_text = f"Month: {start_date.strftime('%Y-%m')}"

        if month:
            try:
                d = datetime.strptime(month, '%Y-%m').date()
                start_date = d.replace(day=1)
                next_month = (d + timedelta(days=32)).replace(day=1)
                end_date = next_month - timedelta(days=1)
                title_text = f"Month: {month}"
            except ValueError:
                await interaction.response.send_message("❌ Invalid month format. Use YYYY-MM.", ephemeral=True)
                return

        # 1. Get All Docs in Range
        query = {
            "date": {
                "$gte": start_date.strftime('%Y-%m-%d'),
                "$lte": end_date.strftime('%Y-%m-%d')
            }
        }
        daily_docs = await self.daily_col.find(query).to_list(length=None)

        # 2. Aggregation {user_id: duration}
        user_totals = {}
        # Also need map for ID -> Name
        user_names = {} 

        for doc in daily_docs:
            uid = doc['user_id']
            dur = doc.get('total_duration', 0)
            user_totals[uid] = user_totals.get(uid, 0) + dur
            user_names[uid] = doc.get('user_name', str(uid))
        
        # 3. Sort
        reverse = True # Default Descending
        if sort and sort.value == "asc":
            reverse = False
            
        sorted_users = sorted(user_totals.items(), key=lambda item: item[1], reverse=reverse)
        
        # 4. Build Embed
        embed = discord.Embed(title="🏆 Voice Leaderboard", description=f"**{title_text}**", color=discord.Color.gold())
        
        desc = ""
        for i, (uid, total_sec) in enumerate(sorted_users, 1):
            name = user_names.get(uid, f"User {uid}") # Fallback name
            time_str = self.format_duration(total_sec)
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**#{i}**"
            desc += f"{medal} **{name}**: {time_str}\n"
        
        if not desc:
            desc = "No activity recorded for this period."
            
        embed.description += "\n\n" + desc
        await interaction.response.send_message(embed=embed)

    def format_duration(self, seconds):
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}h {m}m"
        return f"{m}m {s}s"

async def setup(bot):
    await bot.add_cog(Tracker(bot))
