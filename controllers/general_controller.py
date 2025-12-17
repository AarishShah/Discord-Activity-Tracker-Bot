import discord
from services.general_service import GeneralService
from controllers.attendance_controller import AttendanceController

class GeneralController:
    # Routes that delegate to Attendance Logic
    @staticmethod
    async def away(interaction: discord.Interaction, reason: str):
        await AttendanceController.away(interaction, reason)

    @staticmethod
    async def resume(interaction: discord.Interaction):
        await AttendanceController.resume(interaction)

    # General Logic
    @staticmethod
    async def bhai_count(interaction: discord.Interaction, user: discord.User):
        target = user or interaction.user
        count = await GeneralService.get_bhai_count(target, interaction.guild.id)
        await interaction.response.send_message(f"🧔 **{target.display_name}** has been called 'bhai' **{count}** times.", ephemeral=True)
        
    @staticmethod
    async def on_message(message: discord.Message):
         await GeneralService.process_message(message)
         
    @staticmethod
    async def help_cmd(interaction: discord.Interaction):
        embed = discord.Embed(title="🤖 Bot Commands", color=discord.Color.teal())
        
        # Attendance
        embed.add_field(name="📅 Attendance", value=(
            "`/attendance [status] [date] [reason]` - Mark Present, Half-Day, or Absent\n"
            "`/lunch` - Start lunch break\n"
            "`/drop` - End day (Sign out)"
        ), inline=False)
        
        # General
        embed.add_field(name="⚙️ General", value=(
            "`/away [reason]` - Set status to Away\n"
            "`/resume` - Resume activity (Active)\n"
            "`/bhai-count [user]` - Check 'bhai' count\n"
            "`/cls [limit]` - Clear bot messages"
        ), inline=False)
        
        # Export
        embed.add_field(name="📂 Export", value=(
            "`/csv [start] [end]` - Download Activity Report"
        ), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @staticmethod
    async def cls(interaction: discord.Interaction, limit: int):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=limit, check=lambda m: m.author == interaction.client.user)
        await interaction.followup.send(f"🧹 Cleared {len(deleted)} messages.", ephemeral=True)
