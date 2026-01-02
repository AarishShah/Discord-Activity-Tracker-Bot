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
    async def bhai_count(interaction: discord.Interaction, user: discord.Member, leaderboard_view: str):
        if leaderboard_view:
            await GeneralController.bhai_count_leaderboard(interaction, leaderboard_view)
        else:
            # Default to self if no user provided
            target = user or interaction.user
            await GeneralController.bhai_count_user(interaction, target)

    @staticmethod
    async def bhai_count_user(interaction: discord.Interaction, target: discord.Member):
        count = await GeneralService.get_bhai_count(target, interaction.guild.id)
        await interaction.response.send_message(f"🧔 **{target.display_name}** has searched for his 'bhai' **{count}** times.", ephemeral=False)

    @staticmethod
    async def bhai_count_leaderboard(interaction: discord.Interaction, view_mode: str):
        users = []
        title = "🏆 Bhai Leaderboard"
        
        if view_mode == "top_5":
            users = await GeneralService.get_top_bhai_users(limit=5)
            title = "🏆 Top 5 'Bhai' Callers"
        elif view_mode == "lower_5":
            users = await GeneralService.get_bottom_bhai_users(limit=5)
            title = "📉 Lower 5 'Bhai' Callers"
        elif view_mode == "all":
            users = await GeneralService.get_all_bhai_users()
            title = "📜 Complete 'Bhai' Global Leaderboard"
            
        if not users:
            await interaction.response.send_message("No data found.", ephemeral=False)
            return
        
        lines = []
        for i, doc in enumerate(users, 1):
            name = doc.get('display_name', 'Unknown')
            count = doc.get('global_bhai_count', 0)
            lines.append(f"**{i}. {name}**: {count}")
            
        # Paginate if too long (Discord Limit 4096). Simple logic for now.
        content = "\n".join(lines)
        if len(content) > 4000:
            content = content[:3900] + "\n...(truncated)"
            
        embed = discord.Embed(title=title, description=content, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)
        
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
            "`/bhai-count [user] [leaderboard]` - Check stats or Leaderboard (Top 5, Lower 5, All)\n"
            "`/update` - (Admin) Sync global stats from history"
        ), inline=False)
        
        # Export
        embed.add_field(name="📂 Export", value=(
            "`/csv [start] [end]` - Download Activity Report\n"
            "`/sync [start] [end]` - Manual Google Sheets Sync\n"
            "`/sheet [id] [start] [end]` - Export to new/specific Sheet"
        ), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
