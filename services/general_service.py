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
        
        # Increment Global Count (Stored in Users collection)
        await UserModel.increment_bhai_count(user_id, user_name)

    @classmethod
    async def get_bhai_count(cls, user, guild_id):
        # Fetch from Global User Model
        return await UserModel.get_bhai_count(user.id)
        
    @classmethod
    async def get_top_bhai_users(cls, limit=5):
        return await UserModel.get_top_bhai_users(limit)

    @classmethod
    async def get_bottom_bhai_users(cls, limit=5):
        return await UserModel.get_bottom_bhai_users(limit)

    @classmethod
    async def get_all_bhai_users(cls):
        return await UserModel.get_all_bhai_users()

    @classmethod
    async def get_bhai_rank(cls, user):
        return await UserModel.get_bhai_rank(user.id)

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
                 # Check Leaderboard Before
                 top_before = await UserModel.get_top_bhai_users(limit=1)
                 old_king = top_before[0] if top_before else None
                 
                 # Increment
                 await cls.increment_bhai(message.author.id, message.author.display_name, message.guild.id)
                 
                 # Check Leaderboard After
                 top_after = await UserModel.get_top_bhai_users(limit=1)
                 new_king = top_after[0] if top_after else None
                 
                 # Surpass Logic
                 if old_king and new_king and old_king['_id'] != new_king['_id']:
                     # Verify the message author is the new king
                     if str(new_king['_id']) == str(message.author.id):
                         old_name = old_king.get('display_name', 'Unknown')
                         new_name = new_king.get('display_name', 'Unknown')
                         new_count = new_king.get('global_bhai_count', 0)
                         
                         import random
                         trolls = [
                             f"Sit down {old_name}, there's a new Bhai in town!",
                             f"{old_name} fell off. {new_name} is the captain now.",
                             f"Imagine losing your spot to {new_name}. Couldn't be me, {old_name}.",
                             f"{new_name} just cooked {old_name}. 🍳",
                             f"Game over {old_name}. {new_name} has taken the lead!"
                         ]
                         troll = random.choice(trolls)
                         
                         await message.channel.send(f"👑 **LEADERBOARD UPDATE**: **{new_name}** has surpassed **{old_name}** with **{new_count}** searches!\n*{troll}*")
        
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
