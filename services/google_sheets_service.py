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
    async def export_to_sheet(cls, sheet_id_or_url, rows):
        """
        Exports data to the specified Google Sheet.
        Appends data? Or Overwrites? 
        Let's assume we want to clear and write new report, or append to a specific worksheet?
        For a "Report", usually a new sheet (tab) is best.
        """
        client = cls.get_client()
        
        try:
            # Open by ID or URL
            if "docs.google.com" in sheet_id_or_url:
                sh = client.open_by_url(sheet_id_or_url)
            else:
                sh = client.open_by_key(sheet_id_or_url)
        except Exception as e:
            return {"success": False, "message": f"Failed to open sheet: {str(e)}"}

        # Create a new worksheet for this report with timestamp
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        title = f"Report_{timestamp}"
        
        try:
            worksheet = sh.add_worksheet(title=title, rows=len(rows)+10, cols=len(rows[0])+5)
        except:
            # Fallback if max sheets reached or error, try first sheet? 
            # Or just fail. Let's try to just write to a new sheet.
            return {"success": False, "message": "Failed to create new worksheet. Structure might be full."}
            
        # Write Data
        try:
            # Explicitly use update with range_name and values for gspread v6+
            worksheet.update(range_name='A1', values=rows)
            
            return {"success": True, "message": f"Exported to Sheet specified! Tab: {title}", "url": f"{sh.url}"}
        except Exception as e:
             return {"success": False, "message": f"Failed to write data: {str(e)}"}
    @classmethod
    async def append_daily_stats(cls, rows, month_name):
        """
        Appends daily stats to a sheet named after the month.
        rows: List of lists. Row 0 = Headers.
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

        # Check/Create Worksheet
        try:
             worksheet = sh.worksheet(month_name)
        except gspread.WorksheetNotFound:
             # Create new
             worksheet = sh.add_worksheet(title=month_name, rows=1000, cols=20)
             # Add Headers (First row of input)
             worksheet.update(range_name='A1', values=[rows[0]])
             # Remove header from rows to append
             rows = rows[1:]
        
        if not rows:
             return {"success": True, "message": "No data to append (only headers)."}

        # Append Data
        try:
             # append_rows is safer for adding to bottom
             worksheet.append_rows(rows)
             return {"success": True, "message": f"Appended data to {month_name}"}
        except Exception as e:
             return {"success": False, "message": f"Failed to append: {e}"}
