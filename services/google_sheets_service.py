import gspread
import os
from datetime import datetime, timedelta, date
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
    def get_spreadsheet(cls):
        """
        Opens and returns the Google Spreadsheet specified in GOOGLE_SHEET_ID env var.
        """
        sheet_id_or_url = os.getenv("GOOGLE_SHEET_ID")
        if not sheet_id_or_url:
            raise ValueError("GOOGLE_SHEET_ID not set in .env")

        client = cls.get_client()
        if "docs.google.com" in sheet_id_or_url:
            return client.open_by_url(sheet_id_or_url)
        else:
            return client.open_by_key(sheet_id_or_url)

    @classmethod
    def extract_dates_from_col_a(cls, worksheet):
        """
        Reads Column A of the worksheet and parses all cells in YYYY-MM-DD format.
        Returns a sorted list of unique datetime.date objects found.
        """
        try:
            col_a = worksheet.col_values(1)
        except Exception as e:
            print(f"[GoogleSheetsService] Error reading column A: {e}")
            return []

        found_dates = []
        for val in col_a:
            val_str = str(val).strip()
            if not val_str:
                continue
            try:
                d = datetime.strptime(val_str, "%Y-%m-%d").date()
                found_dates.append(d)
            except ValueError:
                continue
        return sorted(list(set(found_dates)))

    @classmethod
    def get_last_recorded_date(cls, sh, target_year: int):
        """
        Detects the last recorded date in the Google Sheet.
        Checks {target_year} Attendance first, then {target_year - 1} Attendance.
        Returns datetime.date or None.
        """
        for y in [target_year, target_year - 1]:
            tab_name = f"{y} Attendance"
            try:
                ws = sh.worksheet(tab_name)
                dates = cls.extract_dates_from_col_a(ws)
                if dates:
                    return dates[-1]
            except gspread.WorksheetNotFound:
                continue
            except Exception as e:
                print(f"[GoogleSheetsService] Error checking worksheet '{tab_name}': {e}")
                continue
        return None

    @classmethod
    async def detect_missing_dates(cls, target_yesterday, sh=None):
        """
        Inspects the target Google Sheet's existing date entries in Column A.
        Identifies all missing dates between the last recorded date and target_yesterday (inclusive).
        If no recorded dates are found in the sheet, defaults to starting from the 1st of the current month.
        Returns a list of datetime.date objects in ascending chronological order.
        """
        if isinstance(target_yesterday, datetime):
            target_yesterday = target_yesterday.date()

        if sh is None:
            sh = cls.get_spreadsheet()

        last_date = cls.get_last_recorded_date(sh, target_yesterday.year)

        if last_date is None:
            # Brand new tab/sheet: start backfilling from 1st of the current month up to yesterday
            start_date = target_yesterday.replace(day=1)
        else:
            start_date = last_date + timedelta(days=1)

        if start_date > target_yesterday:
            # Sheet is already up to date
            return []

        missing_dates = []
        curr = start_date
        while curr <= target_yesterday:
            missing_dates.append(curr)
            curr += timedelta(days=1)

        return missing_dates

    @classmethod
    async def get_or_create_year_spreadsheet(cls, year):
        """
        Finds a spreadsheet named 'Activity_Tracker_{year}'.
        If not found, creates it.
        Returns the spreadsheet object.
        """
        client = cls.get_client()
        sheet_name = f"Activity_Tracker_{year}"
        
        try:
            sh = client.open(sheet_name)
            return sh
        except gspread.SpreadsheetNotFound:
            print(f"Spreadsheet '{sheet_name}' not found. Creating...")
            sh = client.create(sheet_name)
            return sh

    @classmethod
    async def append_daily_stats(cls, data_payload, date_obj, sh=None):
        """
        Appends daily stats to Year-based tabs: '{Year} Attendance' and '{Year} Voice Stats'.
        data_payload: { 'attendance': rows, 'voice': rows } (or list for backward compatibility)
        """
        try:
            if sh is None:
                sh = cls.get_spreadsheet()
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
        
        # Process Attendance -> "{Year} Attendance"
        if attendance_rows:
            res_att = cls._append_data_to_year_tab(sh, year_str, "Attendance", attendance_rows, date_obj)
            results.append(res_att)
            
        # Process Voice -> "{Year} Voice Stats"
        if voice_rows:
            res_voice = cls._append_data_to_year_tab(sh, year_str, "Voice Stats", voice_rows, date_obj)
            results.append(res_voice)
            
        is_all_skipped = len(results) > 0 and all("(already logged)" in r for r in results)
        return {
            "success": True,
            "skipped": is_all_skipped,
            "message": f"Processed {len(results)} tabs: {', '.join(results)}"
        }

    @classmethod
    def _append_data_to_year_tab(cls, sh, year_str, suffix, rows, date_obj):
        """
        Helper to append rows to a specific Year+Suffix tab.
        Ensures idempotency (no duplicate dates) and prevents duplicated month headers.
        """
        tab_name = f"{year_str} {suffix}"
        date_str = date_obj.strftime("%Y-%m-%d")
        
        try:
            worksheet = sh.worksheet(tab_name)
            
            # Read Column A to check existing dates and headers
            col_a = worksheet.col_values(1)
            col_a_trimmed = [str(v).strip() for v in col_a]
            
            # Idempotency check: skip if date is already present in this sheet
            if date_str in col_a_trimmed:
                print(f"[{tab_name}] Date {date_str} already present in column A. Skipping append.")
                return f"{tab_name} (already logged)"
            
            # Month Separator Logic:
            # Ensure month headers/separators are created once per month transition and never repeated
            month_label = date_obj.strftime("%B").upper()
            col_a_upper = [v.upper() for v in col_a_trimmed if v]
            
            separator_rows = []
            if month_label not in col_a_upper:
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
                    next_row = len(col_a) + 1
                    
                    # Check if we need to resize rows
                    current_row_count = worksheet.row_count
                    needed_rows = next_row + len(final_rows_to_append)
                    
                    if needed_rows > current_row_count:
                        worksheet.add_rows(needed_rows - current_row_count)
                    
                    # Check if we need to resize columns
                    current_col_count = worksheet.col_count
                    needed_cols = max(len(r) for r in final_rows_to_append)
                    if needed_cols > current_col_count:
                        worksheet.add_cols(needed_cols - current_col_count)
                    
                    # Explicitly update starting at A{next_row}
                    worksheet.update(range_name=f'A{next_row}', values=final_rows_to_append)

        except gspread.WorksheetNotFound:
            # Create new
            needed_cols = max(len(rows[0]), 20) if rows else 20
            worksheet = sh.add_worksheet(title=tab_name, rows=1000, cols=needed_cols)
            
            # NEW SHEET LAYOUT
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
                needed_cols_final = max(len(r) for r in final_values)
                if needed_cols_final > worksheet.col_count:
                    worksheet.add_cols(needed_cols_final - worksheet.col_count)
                
                worksheet.update(range_name='A1', values=final_values)
        
        # Apply Word Wrap to the entire sheet
        try:
            last_col = worksheet.col_count
            def col_to_letter(n):
                string = ""
                while n > 0:
                    n, remainder = divmod(n - 1, 26)
                    string = chr(65 + remainder) + string
                return string
            
            last_col_letter = col_to_letter(last_col)
            worksheet.format(f"A:{last_col_letter}", {"wrapStrategy": "WRAP"})
        except Exception as e:
            print(f"Warning: Failed to apply word wrap: {e}")

        return tab_name
