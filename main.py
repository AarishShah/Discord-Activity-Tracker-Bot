import discord
import os
import asyncio
from config import settings
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    
    target_guild_id = os.getenv("TARGET_GUILD_ID")
    try:
        if target_guild_id:
            guild = discord.Object(id=int(target_guild_id))
            # Copy global commands to guild
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f'✅ Synced {len(synced)} command(s) to Guild {target_guild_id} (Instant update)')
        else:
            synced = await bot.tree.sync()
            print(f'Synced {len(synced)} command(s) globally (May take up to 1 hour)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')
    print('------')

async def load_extensions():
    # Only load if the directory exists
    if os.path.exists('./cogs'):
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await bot.load_extension(f'cogs.{filename[:-3]}')
                    print(f'Loaded extension: {filename}')
                except Exception as e:
                    print(f'Failed to load extension {filename}: {e}')
                    import traceback
                    traceback.print_exc()

async def main():
    async with bot:
        await load_extensions()
        if not settings.TOKEN:
            print("Error: DISCORD_TOKEN not found. Please check your .env file.")
            return
        await bot.start(settings.TOKEN)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        pass
