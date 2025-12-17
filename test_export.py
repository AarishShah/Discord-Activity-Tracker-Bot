import discord
import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

from services.export_service import ExportService
from services.google_sheets_service import GoogleSheetsService
from database.connection import Database
from utils.time_utils import get_ist_time

# Load environment
load_dotenv()

# Setup Intent
intents = discord.Intents.default()
intents.members = True # Needed to fetch members

class TestBot(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print(f"Available Guilds: {[f'{g.name} ({g.id})' for g in self.guilds]}")
        
        target_guild_id = os.getenv("TARGET_GUILD_ID")
        if not target_guild_id:
            print("❌ TARGET_GUILD_ID not found in .env")
            await self.close()
            return

        guild = self.get_guild(int(target_guild_id))
        if not guild:
            # Need to fetch if not in cache immediately?
            print(f"⚠️ Guild {target_guild_id} not found in cache. Fetching...")
            try:
                guild = await self.fetch_guild(int(target_guild_id))
            except Exception as e:
                print(f"❌ Failed to fetch guild: {e}")
                await self.close()
                return

        print(f"✅ Found Guild: {guild.name}")
        
        # Simulate "Yesterday"
        now = get_ist_time()
        yesterday = now - timedelta(days=7)
        yesterday_str = yesterday.strftime('%Y-%m-%d')
        month_name = yesterday.strftime('%B')
        
        print(f"🚀 Starting Export for {yesterday_str}...")
        
        try:
            # Replicating Scheduler Logic
            rows = await ExportService.fetch_activity_data(guild, yesterday_str, yesterday_str)
            result = await GoogleSheetsService.append_daily_stats(rows, month_name)
            
            if result['success']:
                print(f"✅ Export Success: {result['message']}")
            else:
                print(f"❌ Export Failed: {result['message']}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"❌ Error: {e}")
            
        print("Done. Closing.")
        await self.close()

async def main():
    # Connect DB (Important!)
    Database.connect()
    
    bot = TestBot(intents=intents)
    token = os.getenv("DISCORD_TOKEN")
    await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
