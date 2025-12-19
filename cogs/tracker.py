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

    @app_commands.command(name="today", description="Get daily stats for a user")
    @app_commands.describe(user="User to check stats for")
    async def today(self, interaction: discord.Interaction, user: discord.Member = None):
        await TrackerController.today_stats(interaction, user)


async def setup(bot):
    await bot.add_cog(Tracker(bot))
