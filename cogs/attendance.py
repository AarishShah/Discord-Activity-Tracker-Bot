import discord
from discord import app_commands
from discord.ext import commands
from controllers.attendance_controller import AttendanceController

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
        await AttendanceController.attendance(interaction, status.value)

    @app_commands.command(name="lunch", description="Start lunch break")
    async def lunch(self, interaction: discord.Interaction):
        await AttendanceController.lunch(interaction)

    @app_commands.command(name="drop", description="Finish the day (Sign out)")
    async def drop(self, interaction: discord.Interaction):
        await AttendanceController.drop(interaction)

    @app_commands.command(name="absent", description="Mark yourself absent")
    @app_commands.describe(reason="Reason for absence", date="Date of absence (YYYY-MM-DD)")
    async def absent(self, interaction: discord.Interaction, date: str, reason: str = "Absent"):
        await AttendanceController.absent(interaction, date, reason)

async def setup(bot):
    await bot.add_cog(Attendance(bot))
