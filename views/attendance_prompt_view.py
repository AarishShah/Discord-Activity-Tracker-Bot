import discord
from services.attendance_service import AttendanceService
from utils.time_utils import get_ist_time

class AttendancePromptView(discord.ui.View):
    def __init__(self, target_member: discord.Member, is_late: bool = False, timeout: float = 600.0):
        super().__init__(timeout=timeout)
        self.target_member = target_member
        self.is_late = is_late
        self.message: discord.Message = None

        # Build dynamic buttons
        if not self.is_late:
            present_button = discord.ui.Button(
                label="Present",
                style=discord.ButtonStyle.success,
                custom_id="prompt_present",
                emoji="🟢"
            )
            present_button.callback = self._create_callback("Present", "Present")
            self.add_item(present_button)

        half_join_button = discord.ui.Button(
            label="Half Day (Joining)",
            style=discord.ButtonStyle.primary,
            custom_id="prompt_half_join",
            emoji="🌅"
        )
        half_join_button.callback = self._create_callback("joining_mid_day", "Half Day (Joining After Mid Day)")
        self.add_item(half_join_button)

        half_leave_button = discord.ui.Button(
            label="Half Day (Leaving)",
            style=discord.ButtonStyle.secondary,
            custom_id="prompt_half_leave",
            emoji="🌇"
        )
        half_leave_button.callback = self._create_callback("leaving_mid_day", "Half Day (Leaving After Mid Day)")
        self.add_item(half_leave_button)

        absent_button = discord.ui.Button(
            label="Absent",
            style=discord.ButtonStyle.danger,
            custom_id="prompt_absent",
            emoji="❌"
        )
        absent_button.callback = self._create_callback("Absent", "Absent")
        self.add_item(absent_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target_member.id:
            await interaction.response.send_message(
                f"❌ This attendance prompt is for {self.target_member.mention}.",
                ephemeral=True
            )
            return False
        return True

    def _create_callback(self, status_value: str, display_name: str):
        async def button_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            guild_id = interaction.guild.id if interaction.guild else None
            if not guild_id:
                await interaction.followup.send("❌ Guild not found.", ephemeral=True)
                return

            if status_value == "Absent":
                today_str = get_ist_time().strftime('%Y-%m-%d')
                result = await AttendanceService.mark_absent(
                    user_id=interaction.user.id,
                    user_name=interaction.user.display_name,
                    guild_id=guild_id,
                    date_str=today_str,
                    reason="Absent (via Voice Prompt)"
                )
            else:
                result = await AttendanceService.mark_attendance(
                    user_id=interaction.user.id,
                    user_name=interaction.user.display_name,
                    guild_id=guild_id,
                    status_value=status_value
                )

            if result.get("success"):
                # Disable all buttons upon successful logging
                for child in self.children:
                    child.disabled = True
                self.stop()

                if interaction.message:
                    try:
                        await interaction.message.edit(
                            content=f"✅ {self.target_member.mention} has logged attendance as **{display_name}**.",
                            view=self
                        )
                    except Exception as e:
                        print(f"[AttendancePromptView] Error updating message: {e}")

                await interaction.followup.send(f"✅ {result['message']}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ {result['message']}", ephemeral=True)

        return button_callback

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass
