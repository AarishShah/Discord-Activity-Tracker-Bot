import csv
import io
import discord
from datetime import datetime, timedelta
from models.attendance_model import AttendanceModel
from models.voice_model import VoiceModel
from models.user_model import UserModel

class ExportService:
    @classmethod
    async def fetch_activity_data(cls, guild, start_date, end_date):
        """
        Fetches and structures activity data for export.
        Returns:headers (list), rows (list of lists)
        """
        guild_id = guild.id
        
        # 1. Fetch Data
        attendance_logs = await AttendanceModel.get_logs_in_range(guild_id, start_date, end_date)
        voice_logs = await VoiceModel.get_stats(None, guild_id, start_date, end_date)
        
        # 2. Organize Data
        attendance_map = {}
        for log in attendance_logs:
            d = log['date']
            u = log['user_id']
            if d not in attendance_map: attendance_map[d] = {}
            attendance_map[d][u] = log
            
        voice_map = {}
        for log in voice_logs:
            d = log['date']
            u = log['user_id']
            if d not in voice_map: voice_map[d] = {}
            voice_map[d][u] = log
            
        # 3. Identify all Users
        all_user_ids = set()
        user_names = {} # {id: name}
        
        # Add all current guild members
        for member in guild.members:
            if not member.bot:
                all_user_ids.add(member.id)
                user_names[member.id] = member.display_name
        
        # Add historical users
        for log in attendance_logs:
            uid = log['user_id']
            all_user_ids.add(uid)
            if uid not in user_names and 'user_name' in log: 
                user_names[uid] = log['user_name']
            
        for log in voice_logs:
            uid = log['user_id']
            all_user_ids.add(uid)
            if uid not in user_names and 'user_name' in log:
                 user_names[uid] = log['user_name']
            
        sorted_users = sorted(list(all_user_ids), key=lambda x: user_names.get(x, str(x)))
        
        # 4. Generate Date Range
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            # Fallback or re-raise
            start_dt = datetime.now()
            end_dt = datetime.now()
            
        delta = end_dt - start_dt
        
        date_list = []
        for i in range(delta.days + 1):
            day = start_dt + timedelta(days=i)
            date_list.append(day)

        # 5. Build Rows
        headers = ["Date"]
        for uid in sorted_users:
            name = user_names.get(uid, f"User {uid}")
            headers.append(f"{name} (Voice, Overtime)")
        
        rows = [headers]
        
        for day in date_list:
            day_str = day.strftime('%Y-%m-%d')
            row = [day_str]
            
            is_weekend = day.weekday() >= 5
            
            for uid in sorted_users:
                # Get Data
                att_record = attendance_map.get(day_str, {}).get(uid)
                voice_record = voice_map.get(day_str, {}).get(uid)
                
                # Determine Status
                if is_weekend:
                    status = "Holiday"
                elif att_record:
                    status = att_record.get('attendance_status', 'Absent')
                else:
                    status = "Absent"
                
                # Determine Voice
                reg_mins = 0
                ot_mins = 0
                
                if voice_record:
                    reg_sec = voice_record.get('total_duration', 0)
                    ot_sec = voice_record.get('overtime_duration', 0)
                    reg_mins = int(round(reg_sec / 60))
                    ot_mins = int(round(ot_sec / 60))
                    
                cell_value = f"{status} ({reg_mins}, {ot_mins})"
                row.append(cell_value)
            
            rows.append(row)
            
        return rows

    @classmethod
    async def generate_csv_report(cls, guild, start_date, end_date):
        rows = await cls.fetch_activity_data(guild, start_date, end_date)
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(rows)
            
        output.seek(0)
        return discord.File(fp=output, filename=f"Activity_Report_{start_date}_to_{end_date}.csv")

    @classmethod
    async def generate_sheet_report(cls, guild, start_date, end_date, sheet_id_or_url):
        from services.google_sheets_service import GoogleSheetsService
        
        rows = await cls.fetch_activity_data(guild, start_date, end_date)
        
        # Export to Sheets
        result = await GoogleSheetsService.export_to_sheet(sheet_id_or_url, rows)
        return result
