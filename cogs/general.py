import discord
from discord import app_commands
from discord.ext import commands
import utils

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="away", description="Set your status to Away")
    @app_commands.describe(reason="Why are you away?")
    async def away(self, interaction: discord.Interaction, reason: str = "AFK"):
        def _txn(data):
            data['status'] = 'Away'
            data['status_reason'] = reason
        
        utils.update_user(interaction.user.id, _txn)
        await interaction.response.send_message(f"🌑 Status set to **Away**: {reason}")

    @app_commands.command(name="back", description="Clear Away status")
    async def back(self, interaction: discord.Interaction):
        def _txn(data):
            data['status'] = 'Active'
            data['status_reason'] = ""
        
        utils.update_user(interaction.user.id, _txn)
        await interaction.response.send_message("🟢 Welcome back!")

    @app_commands.command(name="bhai-count", description="Check how many times 'bhai' has been used")
    async def bhai_count(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = utils.get_user(target.id)
        count = data.get('bhai_count', 0) if data else 0
        
        await interaction.response.send_message(f"**{target.display_name}** has said 'bhai' **{count}** times.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # 1. Bhai Counter
        if "bhai" in message.content.lower():
            def _inc(data):
                data['bhai_count'] = data.get('bhai_count', 0) + 1
            utils.update_user(message.author.id, _inc)
        
        # 2. Away/Leave Auto-Reply
        # Check mentions
        if message.mentions:
            for user in message.mentions:
                data = utils.get_user(user.id)
                if data:
                    status = data.get('status')
                    if status in ['Away', 'Leave']:
                        reason = data.get('status_reason', 'No reason provided')
                        if status == 'Leave':
                            await message.channel.send(f"⚠️ **{user.display_name}** is on leave: {reason}")
                        else:
                            await message.channel.send(f"⚠️ **{user.display_name}** is currently away: {reason}")
    
    @app_commands.command(name="cls", description="Clear messages sent by the bot")
    @app_commands.describe(limit="Number of messages to check (default 20)")
    async def cls(self, interaction: discord.Interaction, limit: int = 20):
        # Defers interaction since deletion can take time
        await interaction.response.defer(ephemeral=True)
        
        deleted = 0
        try:
            # Check history
            async for message in interaction.channel.history(limit=limit):
                if message.author == self.bot.user:
                    await message.delete()
                    deleted += 1
            
            await interaction.followup.send(f"🧹 Cleared {deleted} messages.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to clear messages: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(General(bot))
