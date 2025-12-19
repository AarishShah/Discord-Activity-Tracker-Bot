import discord
from discord import app_commands
from discord.ext import commands
from controllers.export_controller import ExportController

from utils.discord_utils import validate_channel

class Export(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await validate_channel(interaction)

    @app_commands.command(name="csv", description="Download Activity Report as CSV")
    @app_commands.describe(start_date="Start Date (YYYY-MM-DD)", end_date="End Date (YYYY-MM-DD)")
    async def csv(self, interaction: discord.Interaction, start_date: str = None, end_date: str = None):
        await ExportController.download_csv(interaction, start_date, end_date)



async def setup(bot):
    await bot.add_cog(Export(bot))
