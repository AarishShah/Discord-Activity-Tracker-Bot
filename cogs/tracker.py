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


async def setup(bot):
    await bot.add_cog(Tracker(bot))
