import discord
from services.attendance_service import AttendanceService

class AttendanceController:
    
    @staticmethod
    async def attendance(interaction: discord.Interaction, status: str, date: str = None):
        result = await AttendanceService.mark_attendance(
            interaction.user.id,
            interaction.user.display_name,
            interaction.guild.id,
            status,
            date
        )
        emoji = "✅" if result['success'] else "❌"
        await interaction.response.send_message(f"{emoji} {result['message']}", ephemeral=True)

    @staticmethod
    async def lunch(interaction: discord.Interaction):
        result = await AttendanceService.start_lunch(interaction.user.id, interaction.guild.id)
        emoji = "🍔" if result['success'] else "❌"
        await interaction.response.send_message(f"{emoji} {result['message']}", ephemeral=True)

    @staticmethod
    async def away(interaction: discord.Interaction, reason: str):
        result = await AttendanceService.set_away(interaction.user.id, interaction.guild.id, reason)
        emoji = "⚠️" if result['success'] else "❌"
        await interaction.response.send_message(f"{emoji} {result['message']}", ephemeral=True)

    @staticmethod
    async def resume(interaction: discord.Interaction):
        result = await AttendanceService.resume_work(interaction.user.id, interaction.guild.id)
        emoji = "✅" if result['success'] else "❌"
        await interaction.response.send_message(f"{emoji} {result['message']}", ephemeral=True)
        
    @staticmethod
    async def drop(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        result = await AttendanceService.drop_day(interaction.user, interaction.guild.id)
        emoji = "👋" if result['success'] else "❌"
        await interaction.followup.send(f"{emoji} {result['message']}")

    @staticmethod
    async def absent(interaction: discord.Interaction, date: str, reason: str):
        await interaction.response.defer(ephemeral=True)
        
        # Default to today if date is None
        if not date:
            from utils.time_utils import get_ist_time
            date = get_ist_time().strftime('%Y-%m-%d')
            
        result = await AttendanceService.mark_absent(
            interaction.user.id,
            interaction.user.display_name,
            interaction.guild.id,
            date,
            reason
        )
        emoji = "✅" if result['success'] else "❌"
        await interaction.followup.send(f"{emoji} {result['message']}")
