import discord
from discord import app_commands
from discord.ext import commands
import utils
from datetime import datetime

class Attendance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="present", description="Mark yourself as present")
    async def present(self, interaction: discord.Interaction):
        # Logic: Check if marked for today. If not, mark.
        now = utils.get_ist_time()
        
        def update_logic(user_data):
            today_str = now.strftime('%Y-%m-%d')
            # Check if already marked
            for entry in user_data['attendance']:
                if entry['date'] == today_str:
                    return False, f"You have already marked attendance for today as **{entry['type']}**."
            
            # Mark
            user_data['attendance'].append({
                "date": today_str,
                "marked_at": now.isoformat(),
                "type": "present"
            })
            return True, "Marked **Present**!"

        user_data = utils.update_user(interaction.user.id, lambda x: None) # ensure user exists
        # Re-read/Update safely (simplified for now)
        success, msg = "available", "logic pending"
        
        # We need a way to return values from the update_func or just do logic outside.
        # Let's do logic inside update_user wrapper if we want atomic, but for this prototype,
        # we can just use the provided utility pattern.
        
        # NOTE: utils.update_user currently returns the *updated* object, but doesn't easily return custom status.
        # Let's refactor slightly to just set data.
        
        # Let's try a direct approach for clarity in this file
        msg = ""
        def _txn(data):
            nonlocal msg
            today_str = now.strftime('%Y-%m-%d')
            # Append always (History mode)
            data['attendance'].append({
                "date": today_str,
                "marked_at": now.isoformat(),
                "type": "present"
            })
            msg = "✅ You have been marked **Present**."

        utils.update_user(interaction.user.id, _txn)
        await interaction.response.send_message(msg)

    @app_commands.command(name="halfday", description="Mark today as half-day")
    @app_commands.choices(half_type=[
        app_commands.Choice(name="Joining Mid Day (Late)", value="joining_mid_day"),
        app_commands.Choice(name="Leaving Mid Day (Early)", value="leaving_mid_day")
    ])
    async def halfday(self, interaction: discord.Interaction, half_type: app_commands.Choice[str]):
        now = utils.get_ist_time()
        msg = ""
        type_label = half_type.name
        type_val = half_type.value

        def _txn(data):
            nonlocal msg
            today_str = now.strftime('%Y-%m-%d')
            
            data['attendance'].append({
                "date": today_str,
                "marked_at": now.isoformat(),
                "type": type_val
            })
            msg = f"✅ Marked **{type_label}**."

        utils.update_user(interaction.user.id, _txn)
        await interaction.response.send_message(msg)

    @app_commands.command(name="break", description="Start a break")
    async def break_cmd(self, interaction: discord.Interaction):
        # User requested to use /back to resume. So this only sets Break.
        msg = ""
        def _txn(data):
            nonlocal msg
            data['status'] = 'Break'
            msg = "Enjoy your meal! 🍔 Status set to **Break**. Use `/back` to resume."
        
        utils.update_user(interaction.user.id, _txn)
        await interaction.response.send_message(msg)

    @app_commands.command(name="drop", description="Finish the day (Sign out)")
    async def drop(self, interaction: discord.Interaction):
        msg = ""
        def _txn(data):
            nonlocal msg
            data['status'] = 'Offline'
            msg = "Good bye! 👋 Day ended."
            
        utils.update_user(interaction.user.id, _txn)
        await interaction.response.send_message(msg)

    @app_commands.command(name="leave", description="Mark yourself on leave")
    @app_commands.describe(reason="Reason for leave (e.g. Vacation, Sick)")
    async def leave(self, interaction: discord.Interaction, reason: str = "On Leave"):
        # Request leave for today
        now = utils.get_ist_time()
        msg = ""
        def _txn(data):
            nonlocal msg
            today_str = now.strftime('%Y-%m-%d')
            
            # Update global status for Auto-Reply
            data['status'] = 'Leave'
            data['status_reason'] = reason

            # Append to Attendance Record
            data['attendance'].append({
                "date": today_str,
                "marked_at": now.isoformat(),
                "type": "leave",
                "reason": reason
            })
            msg = f"✅ Marked as **On Leave**: {reason}"

        utils.update_user(interaction.user.id, _txn)
        await interaction.response.send_message(msg)

async def setup(bot):
    await bot.add_cog(Attendance(bot))
