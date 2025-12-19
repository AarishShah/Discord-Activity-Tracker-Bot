import gspread
import os
from google.oauth2.service_account import Credentials

class GoogleSheetsService:
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    @classmethod
    def get_client(cls):
        # Path to JSON key file
        creds_path = os.getenv("GOOGLE_CREDENTIALS_JSON", "service_account.json")
        
        if not os.path.exists(creds_path):
            raise FileNotFoundError(f"Credential file not found at: {creds_path}")
            
        creds = Credentials.from_service_account_file(creds_path, scopes=cls.SCOPES)
        client = gspread.authorize(creds)
        return client

    @classmethod
    async def get_or_create_year_spreadsheet(cls, year):
        """
        Finds a spreadsheet named 'Activity_Tracker_{year}'.
        If not found, creates it.
        Returns the spreadsheet object.
        """
        client = cls.get_client()
        sheet_name = f"Activity_Tracker_{year}"
        
        # 1. Search for existing sheet
        # listing all main spreadsheets to find match
        # Note: open_by_url/key is faster if we knew it, but here we search by name.
        # This might be slow if there are 1000s of sheets, but usually fine for a bot.
        
        # Optimization: We can try to open by name directly if library supports it, 
        # but gspread usually requires 'open' (by title).
        try:
            sh = client.open(sheet_name)
            return sh
        except gspread.SpreadsheetNotFound:
            # Create new
            print(f"Spreadsheet '{sheet_name}' not found. Creating...")
            sh = client.create(sheet_name)
            # Share with the service account is automatic (it owns it).
            # But the user needs access.
            # We can't share with the user without knowing their email.
            # So we just print the URL.
            # If we had an Admin Email env var, we could share it here.
            # For now, just return it.
            return sh

    @classmethod
    async def export_to_sheet(cls, sheet_id_or_url, data_payload):
        """
        Exports data to a SPECIFIC sheet (manual override).
        """
        # Handle split dict - Default to Attendance for manual exports for now
        rows = []
        if isinstance(data_payload, dict):
             rows = data_payload.get('attendance', [])
        else:
             rows = data_payload
             
        client = cls.get_client()
        try:
            if "docs.google.com" in sheet_id_or_url:
                sh = client.open_by_url(sheet_id_or_url)
            else:
                sh = client.open_by_key(sheet_id_or_url)
        except Exception as e:
            return {"success": False, "message": f"Failed to open sheet: {str(e)}"}

        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        title = f"Report_{timestamp}"
        
        try:
            worksheet = sh.add_worksheet(title=title, rows=len(rows)+10, cols=len(rows[0])+5)
            worksheet.update(range_name='A1', values=rows)
            return {"success": True, "message": f"Exported to {title}", "url": f"{sh.url}"}
        except Exception as e:
             return {"success": False, "message": f"Failed to export: {str(e)}"}

    @classmethod
    async def append_daily_stats(cls, data_payload, date_obj):
        """
        Appends daily stats to Year-based tabs: '{Year} Attendance' and '{Year} Voice Stats'.
        data_payload: { 'attendance': rows, 'voice': rows } (or list for backward compatibility)
        """
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        if not sheet_id:
             return {"success": False, "message": "GOOGLE_SHEET_ID not set in .env"}

        client = cls.get_client()
        
        try:
             # Open Sheet
             sh = client.open_by_key(sheet_id)
        except Exception as e:
             return {"success": False, "message": f"Failed to open sheet: {e}"}

        year_str = date_obj.strftime("%Y")
        
        # Unpack Data
        if isinstance(data_payload, list):
            attendance_rows = data_payload
            voice_rows = []
        else:
            attendance_rows = data_payload.get('attendance', [])
            voice_rows = data_payload.get('voice', [])

        results = []
        
        # Process Attendance -> "2025 Attendance"
        if attendance_rows:
            res_att = cls._append_data_to_year_tab(sh, year_str, "Attendance", attendance_rows, date_obj)
            results.append(res_att)
            
        # Process Voice -> "2025 Voice Stats"
        if voice_rows:
            res_voice = cls._append_data_to_year_tab(sh, year_str, "Voice Stats", voice_rows, date_obj)
            results.append(res_voice)
            
        return {"success": True, "message": f"Processed {len(results)} tabs: {', '.join(results)}"}

    @classmethod
    def _append_data_to_year_tab(cls, sh, year_str, suffix, rows, date_obj):
        """
        Helper to append rows to a specific Year+Suffix tab.
        """
        # User request: "2025 Attendance" and "2025 Voice Stats"
        tab_name = f"{year_str} {suffix}"
        
        try:
             worksheet = sh.worksheet(tab_name)
             
             # Prepare Separator Rows if 1st of Month (Existing Sheet)
             separator_rows = []
             if date_obj.day == 1:
                 month_label = date_obj.strftime("%B").upper()
                 current_headers = rows[0] if rows else []
                 
                 separator_rows = [
                     [], [],                 # 2 Empty rows
                     [month_label],          # Month Name
                     [],                     # 1 Empty Row
                     current_headers         # Headers
                 ]

             # Append Logic
             if len(rows) > 0:
                 data_rows = rows[1:] # rows[0] is headers
                 
                 final_rows_to_append = []
                 if separator_rows:
                     final_rows_to_append = separator_rows + data_rows
                 else:
                     final_rows_to_append = data_rows
                 
                 if final_rows_to_append:
                     # Calculate insertion point (Column A height)
                     # Note: col_values might be expensive on huge sheets, but fine here.
                     # To be safe, we rely on Col 1.
                     col_a = worksheet.col_values(1)
                     next_row = len(col_a) + 1
                     
                     # Check if we need to resize
                     current_row_count = worksheet.row_count
                     needed_rows = next_row + len(final_rows_to_append)
                     
                     if needed_rows > current_row_count:
                         worksheet.add_rows(needed_rows - current_row_count)
                     
                     # Explicitly update starting at A{next_row}
                     # This forces creating new cells at Column A
                     worksheet.update(range_name=f'A{next_row}', values=final_rows_to_append)

        except gspread.WorksheetNotFound:
             # Create new
             worksheet = sh.add_worksheet(title=tab_name, rows=1000, cols=20)
             
             # NEW SHEET LAYOUT
             # Row 1: Tab Name (e.g. "2025 Attendance")
             # Row 2: Empty
             # Row 3: Empty
             # Row 4: Month Name
             # Row 5: Empty
             # Row 6: Data (Headers + Rows)
             
             title_label = tab_name
             month_label = date_obj.strftime("%B").upper()
             
             layout_rows = [
                 [title_label],  # Row 1
                 [],             # Row 2
                 [],             # Row 3
                 [month_label],  # Row 4
                 []              # Row 5
             ]
             
             if len(rows) > 0:
                final_values = layout_rows + rows
                worksheet.update(range_name='A1', values=final_values)
        
        # Apply Word Wrap to the entire sheet (columns A:Z)
        try:
            worksheet.format("A:Z", {"wrapStrategy": "WRAP"})
        except Exception as e:
            print(f"Warning: Failed to apply word wrap: {e}")

        return tab_name
