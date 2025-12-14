import discord
from models.attendance_model import AttendanceModel
from models.user_model import UserModel
from utils.time_utils import get_ist_time

class GeneralService:
    
    @classmethod
    async def increment_bhai(cls, user_id, user_name, guild_id):
        now = get_ist_time()
        today_str = now.strftime('%Y-%m-%d')
        
        # Increment daily count per guild
        await AttendanceModel.create_or_update(
            user_id, guild_id, today_str,
            {
                "$inc": {"bhai_count": 1},
                "$set": {"user_name": user_name}
            }
        )
        
        # Check Total Count for User (Global or Guild? Logic was "daily logs" update)
        # Original code updated daily logs. It didn't seem to update global user tally?
        # Re-reading original `general.py` -> `utils.logs_col.update_one`
        # So it's daily.
        
        # We also need to fetch the new count to display? The user asked for "check 'bhai' count".
        pass

    @classmethod
    async def get_bhai_count(cls, user, guild_id):
        # Count all 'bhai_count' across all daily logs for this user in this guild?
        # Or just today?
        # Original `bhai-count` command:
        # `pipeline = ... match user_id, guild_id ... group sum bhai_count`
        # Let's replicate this aggregation.
        
        pipeline = [
            {"$match": {"user_id": user.id, "guild_id": guild_id}},
            {"$group": {"_id": "$user_id", "total": {"$sum": "$bhai_count"}}}
        ]
        
        # We need direct DB access for aggregate, or add method to Model
        # Let's add aggregate method to AttendanceModel or just access collection via Model
        col = AttendanceModel.get_collection()
        cursor = col.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        
        total = result[0]['total'] if result else 0
        return total

    @classmethod
    async def process_message(cls, message: discord.Message):
        """
        Handles On Message logic:
        1. 'bhai' detection
        2. Auto-Reply for absent/busy users
        """
        # 1. Bhai Count
        if "bhai" in message.content.lower():
            if message.guild:
                 await cls.increment_bhai(message.author.id, message.author.display_name, message.guild.id)
        
        # 2. Auto-Reply
        if message.mentions:
            for mention in message.mentions:
                if mention.bot: continue

                now = get_ist_time()
                today_str = now.strftime('%Y-%m-%d')
                
                # Check DB
                doc = await AttendanceModel.find_by_date(mention.id, message.guild.id, today_str)
                if doc:
                    # Check Absent
                    if doc.get('attendance_status') == 'Absent':
                        reason = doc.get('reason', 'Absent')
                        await message.channel.send(f"⚠️ **{mention.display_name}** is absent today ({today_str}): {reason}")
                        continue
                    
                    # Check Status (Lunch/Away/Drop)
                    commands = doc.get('commands_used', [])
                    if commands:
                        last_cmd = commands[-1]
                        cmd_name = last_cmd.get('command')
                        
                        # Only if Open (no end_time) or Drop
                        if cmd_name == 'drop':
                            await message.channel.send(f"⚠️ **{mention.display_name}** has signed out for the day.")
                        elif cmd_name == 'lunch' and 'end_time' not in last_cmd:
                            await message.channel.send(f"🍔 **{mention.display_name}** is on lunch break.")
                        elif cmd_name == 'away' and 'end_time' not in last_cmd:
                            r = last_cmd.get('reason', 'AFK')
                            await message.channel.send(f"⚠️ **{mention.display_name}** is currently away: {r}")
