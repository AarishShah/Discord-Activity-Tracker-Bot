import discord
from discord import app_commands
from discord.ext import commands
import utils
from datetime import datetime

class Attendance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="attendance", description="Mark your daily attendance")
    @app_commands.describe(status="Choose your attendance status")
    @app_commands.choices(status=[
        app_commands.Choice(name="Present", value="Present"),
        app_commands.Choice(name="Half Day (Joining After Mid Day)", value="joining_mid_day"),
        app_commands.Choice(name="Half Day (Leaving After Mid Day)", value="leaving_mid_day")
    ])
    async def attendance(self, interaction: discord.Interaction, status: app_commands.Choice[str]):
        now = utils.get_ist_time()
        today_str = now.strftime('%Y-%m-%d')
        status_value = status.value
        status_name = status.name
        
        # Check if already marked
        existing = await utils.logs_col.find_one({
            "user_id": interaction.user.id,
            "guild_id": interaction.guild.id,
            "date": today_str
        })
        
        if existing:
            # Check if status is already set to something meaningful
            if existing.get('attendance_status') in ['Present', 'Absent', 'joining_mid_day', 'leaving_mid_day']:
                 await interaction.response.send_message(f"❌ Status already set to **{existing.get('attendance_status')}** for today.", ephemeral=True)
                 return
            
            await interaction.response.send_message("❌ You have already marked specific attendance for today.", ephemeral=True)
            return

        # Prepare Command Entry
        command_entry = {
            "timestamp": now.isoformat()
        }
        
        if status_value == "Present":
            command_entry["command"] = "present"
        else:
            command_entry["command"] = "halfday"
            command_entry["type"] = status_value

        # Upsert Doc
        await utils.logs_col.update_one(
            {"user_id": interaction.user.id, "guild_id": interaction.guild.id, "date": today_str},
            {
                "$set": {
                    "attendance_status": status_value,
                    "user_name": interaction.user.display_name,
                    # Ensure array exists if creating new
                },
                "$push": {
                    "commands_used": command_entry
                }
            },
            upsert=True
        )
        
        await interaction.response.send_message(f"✅ You have been marked **{status_name}**.", ephemeral=True)

    @app_commands.command(name="lunch", description="Start lunch break")
    async def lunch(self, interaction: discord.Interaction):
        now = utils.get_ist_time()
        today_str = now.strftime('%Y-%m-%d')
        
        res = await utils.logs_col.update_one(
            {"user_id": interaction.user.id, "guild_id": interaction.guild.id, "date": today_str},
            {
                "$push": {
                    "commands_used": {
                        "command": "lunch",
                        "timestamp": now.isoformat()
                    }
                }
            }
        )
        
        if res.matched_count == 0:
            await interaction.response.send_message("❌ You must mark **Present** first.", ephemeral=True)
            return
            
            return
            
        await interaction.response.send_message("🍔 Enjoy your meal! Status set to **Lunch**. Use `/resume` to resume.", ephemeral=True)

    @app_commands.command(name="drop", description="Finish the day (Sign out)")
    async def drop(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True) # Defer to prevent timeout
        
        try:
            now = utils.get_ist_time()
            today_str = now.strftime('%Y-%m-%d')
            
            # Find doc
            doc = await utils.logs_col.find_one({"user_id": interaction.user.id, "guild_id": interaction.guild.id, "date": today_str})
            
            if not doc:
                await interaction.followup.send("❌ No attendance record found for today.")
                return
                
            # Find 'present' command
            commands = doc.get('commands_used', [])
            present_cmd = next((c for c in commands if c.get('command') == 'present'), None)
            
            if not present_cmd:
                 await interaction.followup.send("❌ You haven't marked **Present** today.")
                 return
            
            if 'end_time' in present_cmd:
                 await interaction.followup.send("❌ You have already dropped for today.")
                 return

            # Calculate Duration
            # Ensure timestamp is string
            ts = present_cmd.get('timestamp')
            if not ts:
                 await interaction.followup.send("❌ Error: Present timestamp missing.")
                 return
                 
            start_time = datetime.fromisoformat(ts)
            duration = (now - start_time).total_seconds()
            
            # Update: Split into two operations to avoid conflict
            # 1. Update existing 'present' entry
            await utils.logs_col.update_one(
                {
                    "_id": doc['_id'],
                    "commands_used.command": "present"
                },
                {
                    "$set": {
                        "commands_used.$.end_time": now.isoformat(),
                        "commands_used.$.duration": round(duration, 2)
                    }
                }
            )
            
            # 2. Push 'drop' command
            await utils.logs_col.update_one(
                {"_id": doc['_id']},
                {
                    "$push": {
                        "commands_used": {
                             "command": "drop",
                             "timestamp": now.isoformat()
                        }
                    }
                }
            )
            # Trigger Auto-Disconnect for Voice Tracker
            tracker_cog = self.bot.get_cog('Tracker')
            if tracker_cog:
                await tracker_cog.trigger_auto_disconnect(interaction.user)

            await interaction.followup.send(f"👋 Good bye! Day ended. Duration: {round(duration/3600, 2)}h")
            
        except Exception as e:
            print(f"[Error] Drop command failed: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ An error occurred: {e}")

    @app_commands.command(name="absent", description="Mark yourself absent")
    @app_commands.describe(reason="Reason for absence", date="Date of absence (YYYY-MM-DD)")
    async def absent(self, interaction: discord.Interaction, date: str, reason: str = "Absent"):
        await interaction.response.defer(ephemeral=True)
        now = utils.get_ist_time()
        
        # Validate Date
        try:
            d = datetime.strptime(date, '%Y-%m-%d').date()
            target_date_str = date
        except ValueError:
            await interaction.followup.send("❌ Invalid date. Use YYYY-MM-DD")
            return
            
        # Block Past Dates
        if d < now.date():
             await interaction.followup.send("❌ You cannot mark attendance for past dates.")
             return
            
        # Check if already exists
        existing = await utils.logs_col.find_one({"user_id": interaction.user.id, "guild_id": interaction.guild.id, "date": target_date_str})
        if existing and existing.get('attendance_status') in ['Present', 'Absent', 'joining_mid_day', 'leaving_mid_day']:
             await interaction.followup.send(f"❌ Status already set to **{existing.get('attendance_status')}** for {target_date_str}.")
             return
        
        await utils.logs_col.update_one(
            {"user_id": interaction.user.id, "guild_id": interaction.guild.id, "date": target_date_str},
            {
                "$set": {
                    "attendance_status": "Absent",
                    "user_name": interaction.user.display_name,
                    "reason": reason
                },
                "$push": {
                    "commands_used": {
                        "command": "absent",
                        "reason": reason,
                        "timestamp": now.isoformat()
                    }
                }
            },
            upsert=True
        )
        
        await interaction.followup.send(f"✅ Marked as **Absent** on {target_date_str}: {reason}")

async def setup(bot):
    await bot.add_cog(Attendance(bot))
