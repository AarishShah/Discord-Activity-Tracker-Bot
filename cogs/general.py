import discord
from discord import app_commands
from discord.ext import commands
from controllers.general_controller import GeneralController
from services.maintenance_service import MaintenanceService

from utils.discord_utils import validate_channel

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await validate_channel(interaction)



    @app_commands.command(name="bhai-count", description="Check how many times someone has been called 'bhai'")
    @app_commands.describe(user="User to check", mode="Select 'Top 5' to see leaderboard")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Top 5 Users", value="Top 5")
    ])
    async def bhai_count(self, interaction: discord.Interaction, user: discord.Member = None, mode: app_commands.Choice[str] = None):
        show_top = mode.value if mode else None
        await GeneralController.bhai_count(interaction, user, show_top)

    @app_commands.command(name="update", description="Admin: Sync global stats from historical data")
    async def update_stats(self, interaction: discord.Interaction):
        # Optional: Add permission check (e.g. if interaction.user.guild_permissions.administrator:)
        # User requested "temporary command", so we'll keep it simple but maybe log it.
        await interaction.response.defer(ephemeral=False)
        stats = await MaintenanceService.sync_global_stats()
        await interaction.followup.send(f"✅ **Sync Complete**\n- Bhai Counts Updated: {stats['bhai_updates']}\n- Voice Stats Updated: {stats['voice_updates']}")

    @app_commands.command(name="help", description="Show help")
    async def help_cmd(self, interaction: discord.Interaction):
        await GeneralController.help_cmd(interaction)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        await GeneralController.on_message(message)

async def setup(bot):
    await bot.add_cog(General(bot))
