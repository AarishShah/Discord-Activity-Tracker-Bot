import discord
from services.attendance_service import AttendanceService

class AttendanceController:
    
    @staticmethod
    async def attendance(interaction: discord.Interaction, status: str, date: str = None, reason: str = None):
        # 1. Handle Absent Logic
        if status == "Absent":
            await interaction.response.defer(ephemeral=False)
            
            # Default to today if date is None
            if not date:
                from utils.time_utils import get_ist_time
                date = get_ist_time().strftime('%Y-%m-%d')
            
            # Default reason
            if not reason:
                reason = "Absent"
                
            result = await AttendanceService.mark_absent(
                interaction.user.id,
                interaction.user.display_name,
                interaction.guild.id,
                date,
                reason
            )
            emoji = "✅" if result['success'] else "❌"
            await interaction.followup.send(f"{emoji} {result['message']}")
            return

        # 2. Handle Present/HalfDay Logic
        # Validate Date Usage
        if date:
             await interaction.response.send_message("❌ Date parameter is only supported for **Absent** status. Present/Half-Day is always for **Today**.", ephemeral=False)
             return

        result = await AttendanceService.mark_attendance(
            interaction.user.id,
            interaction.user.display_name,
            interaction.guild.id,
            status
        )
        emoji = "✅" if result['success'] else "❌"
        await interaction.response.send_message(f"{emoji} {result['message']}", ephemeral=False)

    @staticmethod
    async def lunch(interaction: discord.Interaction):
        result = await AttendanceService.start_lunch(interaction.user.id, interaction.guild.id)
        emoji = "🍔" if result['success'] else "❌"
        await interaction.response.send_message(f"{emoji} {result['message']}", ephemeral=False)

    @staticmethod
    async def away(interaction: discord.Interaction, reason: str):
        result = await AttendanceService.set_away(interaction.user.id, interaction.guild.id, reason)
        emoji = "⚠️" if result['success'] else "❌"
        await interaction.response.send_message(f"{emoji} {result['message']}", ephemeral=False)

    @staticmethod
    async def resume(interaction: discord.Interaction):
        result = await AttendanceService.resume_work(interaction.user.id, interaction.guild.id)
        emoji = "✅" if result['success'] else "❌"
        await interaction.response.send_message(f"{emoji} {result['message']}", ephemeral=False)
        
    @staticmethod
    async def drop(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        result = await AttendanceService.drop_day(interaction.user, interaction.guild.id)
        
        if result['success']:
             # Show Daily Stats
             from controllers.tracker_controller import TrackerController
             embed = await TrackerController.build_daily_stats_embed(interaction.user, interaction.guild)
             # Prepend the drop confirmation to the description or send as message?
             # User requested "show the same message as ... /today", but likely still wants to know they dropped.
             # We can just send the embed, maybe add the result message in content.
             await interaction.followup.send(content=f"👋 {result['message']}", embed=embed)
        else:
             await interaction.followup.send(f"❌ {result['message']}")
