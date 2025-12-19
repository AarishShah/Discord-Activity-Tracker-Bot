import discord
from discord import app_commands
from discord.ext import commands
from controllers.export_controller import ExportController

class Export(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Restriction: Only allow commands in "attendance" channel
        if interaction.channel and interaction.channel.name == "attendance":
            return True
        
        await interaction.response.send_message("❌ You can only use these commands in the **#attendance** channel.", ephemeral=True)
        return False

    @app_commands.command(name="csv", description="Download Activity Report as CSV")
    @app_commands.describe(start_date="Start Date (YYYY-MM-DD)", end_date="End Date (YYYY-MM-DD)")
    async def csv(self, interaction: discord.Interaction, start_date: str = None, end_date: str = None):
        await ExportController.download_csv(interaction, start_date, end_date)



async def setup(bot):
    await bot.add_cog(Export(bot))
