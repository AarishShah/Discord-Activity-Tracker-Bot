import discord
from datetime import datetime, timedelta
from services.export_service import ExportService
from utils.time_utils import get_ist_time

class ExportController:
    @staticmethod
    async def download_csv(interaction: discord.Interaction, start_date: str = None, end_date: str = None):
        await interaction.response.defer(ephemeral=False)
        
        now = get_ist_time()
        
        # Default: Current Month
        if not start_date:
            start_date = now.replace(day=1).strftime('%Y-%m-%d')
        if not end_date:
            # End of current month logic
            # (First day of next month - 1 day)
            next_month = now.replace(day=28) + timedelta(days=4)
            last_day = next_month - timedelta(days=next_month.day)
            end_date = last_day.strftime('%Y-%m-%d')
            
        # Validation
        try:
            s_dt = datetime.strptime(start_date, '%Y-%m-%d')
            e_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            if s_dt > e_dt:
                await interaction.followup.send("❌ Start date cannot be after End date.", ephemeral=False)
                return
        except ValueError:
            await interaction.followup.send("❌ Invalid date format. Please use YYYY-MM-DD.", ephemeral=False)
            return

        try:
            file = await ExportService.generate_csv_report(interaction.guild, start_date, end_date)
            await interaction.followup.send(content=f"📊 **Activity Report**\n📅 {start_date} to {end_date}", file=file, ephemeral=False)
        except Exception as e:
            print(f"[ExportController] Error: {e}")
            await interaction.followup.send("❌ An error occurred while generating the CSV.", ephemeral=False)

    @staticmethod
    async def export_to_sheets(interaction: discord.Interaction, sheet_id: str, start_date: str = None, end_date: str = None):
        await interaction.response.defer(ephemeral=False)
        
        now = get_ist_time()
        
        # Default: Current Month
        if not start_date:
            start_date = now.replace(day=1).strftime('%Y-%m-%d')
        if not end_date:
            next_month = now.replace(day=28) + timedelta(days=4)
            last_day = next_month - timedelta(days=next_month.day)
            end_date = last_day.strftime('%Y-%m-%d')
            
        # Validation
        try:
            s_dt = datetime.strptime(start_date, '%Y-%m-%d')
            e_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            if s_dt > e_dt:
                await interaction.followup.send("❌ Start date cannot be after End date.", ephemeral=False)
                return
        except ValueError:
            await interaction.followup.send("❌ Invalid date format. Please use YYYY-MM-DD.", ephemeral=False)
            return

        try:
            result = await ExportService.generate_sheet_report(interaction.guild, start_date, end_date, sheet_id)
            if result['success']:
                await interaction.followup.send(content=f"📊 **Google Sheet Updated**\n📅 {start_date} to {end_date}\n🔗 [View Sheet]({result.get('url', '#')})", ephemeral=False)
            else:
                await interaction.followup.send(content=f"❌ Failed to export: {result['message']}", ephemeral=False)
        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=False)
