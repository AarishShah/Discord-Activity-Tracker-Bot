import discord
import os
import asyncio
import config
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

async def load_extensions():
    # Only load if the directory exists
    if os.path.exists('./cogs'):
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await bot.load_extension(f'cogs.{filename[:-3]}')

async def main():
    async with bot:
        await load_extensions()
        if not config.TOKEN:
            print("Error: DISCORD_TOKEN not found. Please check your .env file.")
            return
        await bot.start(config.TOKEN)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        pass
