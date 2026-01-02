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
    async def bhai_count(interaction: discord.Interaction, user: discord.Member = None, show_top: str = None):
        # 1. Top 5 Mode
        if show_top == "Top 5":
            top_users = await GeneralService.get_top_bhai_users(limit=5)
            if not top_users:
                await interaction.response.send_message("No data found.", ephemeral=False)
                return
            
            lines = []
            for i, doc in enumerate(top_users, 1):
                name = doc.get('display_name', 'Unknown')
                count = doc.get('global_bhai_count', 0)
                lines.append(f"**{i}. {name}**: {count}")
                
            embed = discord.Embed(title="🏆 Top 5 'Bhai' Callers", description="\n".join(lines), color=discord.Color.gold())
            await interaction.response.send_message(embed=embed)
            return

        # 2. Specific User or Self
        target = user or interaction.user
        count = await GeneralService.get_bhai_count(target, interaction.guild.id)
        
        await interaction.response.send_message(f"🧔 **{target.display_name}** has been called 'bhai' **{count}** times (Global).", ephemeral=False)
        
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

        # Statistics
        embed.add_field(name="📊 Statistics", value=(
            "`/today [user]` - View daily stats"
        ), inline=False)
        
        # General
        embed.add_field(name="⚙️ General", value=(
            "`/away [reason]` - Set status to Away\n"
            "`/resume` - Resume activity (Active)\n"
            "`/bhai-count [user]` - Check 'bhai' count"
        ), inline=False)
        
        # Export
        embed.add_field(name="📂 Export", value=(
            "`/csv [start] [end]` - Download Activity Report"
        ), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
