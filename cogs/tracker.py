import discord
from discord import app_commands
from discord.ext import commands
from controllers.tracker_controller import TrackerController

from utils.discord_utils import validate_channel

class Tracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await validate_channel(interaction)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot: return
        await TrackerController.on_voice_state_update(member, before, after)

    @app_commands.command(name="stats", description="View attendance and activity statistics")
    @app_commands.describe(
        user="Optional: User to check stats for (defaults to you)",
        preset="Optional: Quick filter preset",
        start_date="Optional: Start Date (YYYY-MM-DD)",
        end_date="Optional: End Date (YYYY-MM-DD)"
    )
    @app_commands.choices(preset=[
        app_commands.Choice(name="Current Day", value="current_day"),
        app_commands.Choice(name="Yesterday", value="yesterday"),
        app_commands.Choice(name="Last Month", value="last_month"),
        app_commands.Choice(name="Current Month", value="current_month")
    ])
    async def stats(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
        preset: app_commands.Choice[str] = None,
        start_date: str = None,
        end_date: str = None
    ):
        preset_val = preset.value if preset else None
        await TrackerController.get_stats(interaction, user, preset_val, start_date, end_date)


async def setup(bot):
    await bot.add_cog(Tracker(bot))
