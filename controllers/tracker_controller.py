import discord
from discord import app_commands
from services.voice_service import VoiceService
from models.attendance_model import AttendanceModel # Need attendance for stats?
from models.user_model import UserModel
from utils.time_utils import get_ist_time
from datetime import datetime, timedelta

class TrackerController:
    
    @staticmethod
    async def on_voice_state_update(member, before, after):
        # JOIN
        if before.channel is None and after.channel is not None:
            VoiceService.start_session(member, after.channel)
        # LEAVE
        elif before.channel is not None and after.channel is None:
            await VoiceService.end_session(member, before.channel, reason="left")
        # SWITCH
        elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
            await VoiceService.end_session(member, before.channel, reason="hopped", silent=True)
            VoiceService.start_session(member, after.channel, silent=True)
            print(f"[Tracker] {member.display_name} hopped from {before.channel.name} to {after.channel.name}")

    @staticmethod
    async def statistic(interaction: discord.Interaction, user: discord.Member = None, date: str = None, month: str = None):
        # Date Logic
        today = get_ist_time().date()
        start_date = today
        end_date = today
        title_date = str(today)

        try:
            if month:
                d = datetime.strptime(month, '%Y-%m').date()
                start_date = d.replace(day=1)
                next_month = d.replace(day=28) + timedelta(days=4)
                end_date = next_month - timedelta(days=next_month.day)
                title_date = f"Month: {month}"
            elif date:
                d = datetime.strptime(date, '%Y-%m-%d').date()
                start_date = d
                end_date = d
                title_date = date
        except ValueError:
             await interaction.response.send_message("❌ Invalid format. Date: YYYY-MM-DD, Month: YYYY-MM", ephemeral=True)
             return

        # Fetch Data
        data = await VoiceService.get_aggregated_stats(
            user.id if user else None, 
            interaction.guild.id, 
            start_date, 
            end_date
        )

        if not user:
            # Global Stats (All Users)
            user_stats = data['user_stats']
            if not user_stats:
                await interaction.response.send_message(f"No activity found for **{title_date}**.", ephemeral=True)
                return

            sorted_users = sorted(user_stats.items(), key=lambda x: x[1]['name']) 
            
            # Chunking
            CHUNK_SIZE = 5
            chunks = [sorted_users[i:i + CHUNK_SIZE] for i in range(0, len(sorted_users), CHUNK_SIZE)]
            
            first = True
            for i, chunk in enumerate(chunks):
                embed = discord.Embed(title=f"📊 Global Statistics ({i+1}/{len(chunks)})", description=f"Activity for **{title_date}**", color=discord.Color.gold())
                for uid, stats in chunk:
                    name = stats['name']
                    time_str = VoiceService.format_duration(stats['total_duration'])
                    count = stats['session_count']
                    embed.add_field(name=f"👤 {name}", value=f"🎙️ **{count}** Sessions\n⏱️ **{time_str}**", inline=False)
                
                if first:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    first = False
                else:
                    await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Single User Stats
        user_name = user.display_name
        duration_str = VoiceService.format_duration(data['total_duration'])
        
        embed = discord.Embed(
            title=f"📊 Statistics for {user_name}",
            description=f"Activity for **{title_date}**",
            color=discord.Color.blue()
        )

        # Check Attendance (Only meaningful for single day)
        if start_date == end_date:
            # We used to fetch from user.attendance logic. 
            # Now attendance is in daily_logs. Let's use AttendanceModel
            doc = await AttendanceModel.find_by_date(user.id, interaction.guild.id, str(start_date))
            status_text = "Not Marked"
            if doc:
                s = doc.get('attendance_status', 'Unknown')
                r = doc.get('reason', '')
                status_text = f"{s}" + (f" ({r})" if r else "")
            embed.add_field(name="📅 Attendance", value=status_text, inline=True)

        embed.add_field(name="🎙️ Voice Sessions", value=str(data['session_count']), inline=True)
        embed.add_field(name="⏱️ Total Voice Time", value=duration_str, inline=True)
        
        channel_stats = data.get('channel_stats', {})
        if channel_stats:
            channels_desc = ""
            for name, dur in channel_stats.items():
                channels_desc += f"• **{name}**: {VoiceService.format_duration(dur)}\n"
            embed.add_field(name="🔊 Channel Breakdown", value=channels_desc, inline=False)
        else:
            embed.add_field(name="🔊 Channel Breakdown", value="No voice activity recorded.", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @staticmethod
    async def leaderboard(interaction: discord.Interaction, month: str = None, sort: str = "desc"):
        today = get_ist_time().date()
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

        # Fetch All Data
        data = await VoiceService.get_aggregated_stats(
             None, # All users
             interaction.guild.id,
             start_date,
             end_date
        )
        
        user_stats = data['user_stats'] # {uid: {total, count, name}}
        
        # Sort
        reverse = (sort == "desc")
        sorted_users = sorted(user_stats.items(), key=lambda x: x[1]['total_duration'], reverse=reverse)
        
        embed = discord.Embed(title="🏆 Voice Leaderboard", description=f"**{title_text}**", color=discord.Color.gold())
        
        desc = ""
        for i, (uid, stats) in enumerate(sorted_users, 1):
            name = stats['name']
            time_str = VoiceService.format_duration(stats['total_duration'])
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**#{i}**"
            desc += f"{medal} **{name}**: {time_str}\n"
            
        if not desc:
            desc = "No activity recorded for this period."
            
        embed.description += "\n\n" + desc
        await interaction.response.send_message(embed=embed, ephemeral=True)
