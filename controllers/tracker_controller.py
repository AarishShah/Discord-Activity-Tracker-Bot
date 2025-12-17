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


