import discord
import os

async def validate_channel(interaction: discord.Interaction) -> bool:
    """
    Validates if the command is being used in the correct channel.
    Prioritizes ATTENDANCE_CHANNEL_ID, then ATTENDANCE_CHANNEL_NAME (default "attendance").
    """
    
    # 1. Check ID
    target_id = os.getenv("ATTENDANCE_CHANNEL_ID")
    if target_id:
        if str(interaction.channel.id) == target_id:
            return True
    
    # 2. Check Name
    target_name = os.getenv("ATTENDANCE_CHANNEL_NAME", "attendance")
    if interaction.channel and interaction.channel.name == target_name:
        return True
    
    # 3. Fail
    msg = f"❌ You can only use these commands in the **#{target_name}** channel."
    await interaction.response.send_message(msg, ephemeral=True)
    return False

def get_log_channel(guild: discord.Guild):
    """
    Finds the correct channel for logging auto-drops/exports.
    """
    target_id = os.getenv("ATTENDANCE_CHANNEL_ID")
    if target_id:
        channel = guild.get_channel(int(target_id))
        if channel: return channel

    target_name = os.getenv("ATTENDANCE_CHANNEL_NAME", "attendance")
    channel = discord.utils.get(guild.text_channels, name=target_name)
    return channel
