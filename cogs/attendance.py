import discord
from discord import app_commands
from discord.ext import commands
from controllers.attendance_controller import AttendanceController

class Attendance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="attendance", description="Mark your daily attendance")
    @app_commands.describe(
        status="Choose your attendance status",
        date="Optional: Date (YYYY-MM-DD) for Absent",
        reason="Optional: Reason for Absent"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="Present", value="Present"),
        app_commands.Choice(name="Half Day (Joining After Mid Day)", value="joining_mid_day"),
        app_commands.Choice(name="Half Day (Leaving After Mid Day)", value="leaving_mid_day"),
        app_commands.Choice(name="Absent", value="Absent")
    ])
    async def attendance(self, interaction: discord.Interaction, status: app_commands.Choice[str], date: str = None, reason: str = None):
        await AttendanceController.attendance(interaction, status.value, date, reason)

    @app_commands.command(name="lunch", description="Start lunch break")
    async def lunch(self, interaction: discord.Interaction):
        await AttendanceController.lunch(interaction)

    @app_commands.command(name="drop", description="Finish the day (Sign out)")
    async def drop(self, interaction: discord.Interaction):
        await AttendanceController.drop(interaction)

async def setup(bot):
    await bot.add_cog(Attendance(bot))
