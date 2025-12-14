import discord
from discord import app_commands
from discord.ext import commands
from controllers.tracker_controller import TrackerController

class Tracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot: return
        await TrackerController.on_voice_state_update(member, before, after)

    @app_commands.command(name="statistic", description="Get activity stats")
    @app_commands.describe(
        user="Specific user (Optional)", 
        date="Date (YYYY-MM-DD) (Optional)", 
        month="Month (YYYY-MM) (Optional)"
    )
    async def statistic(self, interaction: discord.Interaction, user: discord.Member = None, date: str = None, month: str = None):
        await TrackerController.statistic(interaction, user, date, month)

    @app_commands.command(name="leaderboard", description="Show top users by voice activity")
    @app_commands.describe(month="Month (YYYY-MM). Default: Current Month", sort="Sort order (default: Descending)")
    @app_commands.choices(sort=[
        app_commands.Choice(name="Descending (Highest First)", value="desc"),
        app_commands.Choice(name="Ascending (Lowest First)", value="asc")
    ])
    async def leaderboard(self, interaction: discord.Interaction, month: str = None, sort: app_commands.Choice[str] = None):
        sort_val = sort.value if sort else "desc"
        await TrackerController.leaderboard(interaction, month, sort_val)

async def setup(bot):
    await bot.add_cog(Tracker(bot))
