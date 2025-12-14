import discord
from discord import app_commands
from discord.ext import commands
import utils
from datetime import datetime

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="away", description="Set your status to Away")
    @app_commands.describe(reason="Why are you away?")
    async def away(self, interaction: discord.Interaction, reason: str = "AFK"):
        await interaction.response.defer()
        try:
            now = utils.get_ist_time()
            today_str = now.strftime('%Y-%m-%d')
            
            # Must be marked present first
            res = await utils.logs_col.update_one(
                {"user_id": interaction.user.id, "date": today_str},
                {
                    "$push": {
                        "commands_used": {
                            "command": "away",
                            "reason": reason,
                            "timestamp": now.isoformat()
                        }
                    }
                }
            )
            
            if res.matched_count == 0:
                await interaction.followup.send("❌ You must mark **Present** first.")
                return

            await interaction.followup.send(f"🌑 Status set to **Away**: {reason}")
        except Exception as e:
             await interaction.followup.send(f"❌ Error: {e}")

    @app_commands.command(name="resume", description="Clear Away/Break status and resume activity")
    async def resume(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            now = utils.get_ist_time()
            today_str = now.strftime('%Y-%m-%d')
            
            doc = await utils.logs_col.find_one({"user_id": interaction.user.id, "date": today_str})
            
            if not doc:
                await interaction.followup.send("❌ No attendance record found for today.")
                return
                
            # Find Open Event (Lunch or Away without end_time)
            commands = doc.get('commands_used', [])
            target_idx = -1
            target_cmd = None
            
            # Search backwards to find the LATEST open event
            for i in range(len(commands) - 1, -1, -1):
                c = commands[i]
                if c.get('command') in ['lunch', 'away'] and 'end_time' not in c:
                    target_idx = i
                    target_cmd = c
                    break
            
            if target_idx == -1:
                 await interaction.followup.send("❌ Nothing to resume. You are already Active or haven't taken a break.")
                 return

            # Calculate Duration
            start_time = datetime.fromisoformat(target_cmd['timestamp'])
            duration = (now - start_time).total_seconds()
            
            # Update: Split to avoid conflict
            # 1. Close the open status (lunch/away)
            await utils.logs_col.update_one(
                {"_id": doc['_id']},
                {
                    "$set": {
                        f"commands_used.{target_idx}.end_time": now.isoformat(),
                        f"commands_used.{target_idx}.duration": round(duration, 2)
                    }
                }
            )

            # 2. Push 'resume' command
            await utils.logs_col.update_one(
                {"_id": doc['_id']},
                {
                    "$push": {
                        "commands_used": {
                            "command": "resume",
                            "timestamp": now.isoformat()
                        }
                    }
                }
            )
            await interaction.followup.send("🟢 Welcome back! Status set to **Active**.")
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}")

    @app_commands.command(name="bhai-count", description="Check how many times 'bhai' has been used")
    async def bhai_count(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = await utils.get_user(target.id)
        count = data.get('bhai_count', 0) if data else 0
        
        await interaction.response.send_message(f"**{target.display_name}** has said 'bhai' **{count}** times.")

    @app_commands.command(name="help", description="List all available commands")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🤖 Bot Commands", color=discord.Color.green())
        
        # Tracker
        embed.add_field(name="📊 Tracker", value=(
            "`/statistic [user] [date] [month]` - View activity stats\n"
            "`/leaderboard [month] [sort]` - View top users by voice time"
        ), inline=False)
        
        # Attendance
        embed.add_field(name="📅 Attendance", value=(
            "`/present` - Mark present\n"
            "`/halfday [type]` - Mark half-day (Late Join/Early Leave)\n"
            "`/lunch` - Start lunch break\n"
            "`/absent [reason] [date]` - Mark absent (default today)\n"
            "`/drop` - End day (Sign out)"
        ), inline=False)
        
        # General
        embed.add_field(name="⚙️ General", value=(
            "`/away [reason]` - Set status to Away\n"
            "`/resume` - Resume activity (Active)\n"
            "`/bhai-count [user]` - Check 'bhai' count\n"
            "`/cls [limit]` - Clear bot messages"
        ), inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if "bhai" in message.content.lower():
            # 1. Global Count (Users Collection)
            def _inc(data):
                data['bhai_count'] = data.get('bhai_count', 0) + 1
            await utils.update_user(message.author.id, _inc)

            # 2. Daily Count (Daily Logs Collection)
            now = utils.get_ist_time()
            today_str = now.strftime('%Y-%m-%d')
            await utils.logs_col.update_one(
                {"user_id": message.author.id, "date": today_str},
                {
                    "$inc": {"bhai_count": 1},
                    "$set": {"user_name": message.author.display_name}
                },
                upsert=True
            )
        
        # 2. Away/Leave Auto-Reply (Check Daily Logs)
        if message.mentions:
            now = utils.get_ist_time()
            today_str = now.strftime('%Y-%m-%d')
            
            for user in message.mentions:
                # Check Daily Log
                doc = await utils.logs_col.find_one({"user_id": user.id, "date": today_str})
                
                if doc:
                    # Check absent status
                    if doc.get('attendance_status') == 'Absent':
                        reason = doc.get('reason', 'Absent')
                        await message.channel.send(f"⚠️ **{user.display_name}** is absent: {reason}")
                        continue
                    
                    # Check current action (Last command logic)
                    commands = doc.get('commands_used', [])
                    if commands:
                        last_cmd = commands[-1]
                        cmd_name = last_cmd.get('command')
                        
                        # If last command is Lunch or Away (and no resume implies it is still active because Resume pushes new command)
                        # Wait, Resume pushes 'resume'. So if last cmd is 'resume' or 'present', they are Active.
                        # If last cmd is 'lunch' or 'away', then they are inactive.
                        # Wait, 'drop' also means inactive.
                        
                        if cmd_name == 'lunch':
                            await message.channel.send(f"🍔 **{user.display_name}** is on lunch break.")
                        elif cmd_name == 'away':
                            r = last_cmd.get('reason', 'AFK')
                            await message.channel.send(f"⚠️ **{user.display_name}** is currently away: {r}")
                        elif cmd_name == 'drop':
                            await message.channel.send(f"⚠️ **{user.display_name}** has signed out for the day.")
                else:
                    # No record for today = Offline
                    pass # Or say offline? Usually silence is better unless explicitly checked.

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
