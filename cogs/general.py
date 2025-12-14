import discord
from discord import app_commands
from discord.ext import commands
from controllers.general_controller import GeneralController

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="away", description="Set status to Away (AFK)")
    @app_commands.describe(reason="Reason for being away")
    async def away(self, interaction: discord.Interaction, reason: str = "AFK"):
        await GeneralController.away(interaction, reason)

    @app_commands.command(name="resume", description="Resume work (Back from Lunch/Away)")
    async def resume(self, interaction: discord.Interaction):
        await GeneralController.resume(interaction)

    @app_commands.command(name="bhai-count", description="Check how many times someone has been called 'bhai'")
    @app_commands.describe(user="User to check")
    async def bhai_count(self, interaction: discord.Interaction, user: discord.Member = None):
        await GeneralController.bhai_count(interaction, user)

    @app_commands.command(name="help", description="Show help")
    async def help_cmd(self, interaction: discord.Interaction):
        await GeneralController.help_cmd(interaction)

    @app_commands.command(name="cls", description="Clear bot messages")
    async def cls(self, interaction: discord.Interaction, limit: int = 10):
        await GeneralController.cls(interaction, limit)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        await GeneralController.on_message(message)

async def setup(bot):
    await bot.add_cog(General(bot))
