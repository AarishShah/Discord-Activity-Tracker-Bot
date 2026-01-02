import discord
from discord import app_commands
from services.voice_service import VoiceService
from models.attendance_model import AttendanceModel # Need attendance for stats?
from models.voice_model import VoiceModel
from models.user_model import UserModel
from utils.time_utils import get_ist_time
from datetime import datetime, timedelta, timezone

class TrackerController:
    
    @staticmethod
    async def on_voice_state_update(member, before, after):
        # JOIN
        if before.channel is None and after.channel is not None:
            await VoiceService.start_session(member, after.channel)
        # LEAVE
        elif before.channel is not None and after.channel is None:
            await VoiceService.end_session(member, before.channel, reason="left")
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
    async def today_stats(interaction: discord.Interaction, user: discord.Member = None):
        try:
            await interaction.response.defer(ephemeral=False)
            target = user or interaction.user
            embed = await TrackerController.build_daily_stats_embed(target, interaction.guild)
            await interaction.followup.send(embed=embed, ephemeral=False)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=False)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=False)


