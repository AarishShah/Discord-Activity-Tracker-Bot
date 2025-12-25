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

    @app_commands.command(name="sync", description="Sync activity data to the main Google Sheet tracker")
    @app_commands.describe(start_date="Start Date (YYYY-MM-DD)", end_date="End Date (YYYY-MM-DD)")
    async def sync(self, interaction: discord.Interaction, start_date: str = None, end_date: str = None):
        """Manually trigger the daily sync logic for a specific date range."""
        await ExportController.export_to_sheets(interaction, start_date, end_date)

    @app_commands.command(name="sheet", description="Export Activity Report to a NEW worksheet in a Google Sheet")
    @app_commands.describe(
        sheet_id="Google Sheet ID or URL",
        start_date="Start Date (YYYY-MM-DD)", 
        end_date="End Date (YYYY-MM-DD)"
    )
    async def sheet(self, interaction: discord.Interaction, sheet_id: str, start_date: str = None, end_date: str = None):
        """Creates a new worksheet with the report data in the specified Google Sheet."""
        await ExportController.export_to_sheets(interaction, start_date, end_date, sheet_id)

async def setup(bot):
    await bot.add_cog(Export(bot))
