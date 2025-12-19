# Discord Activity Tracker

A Discord bot designed to track user attendance and voice channel activity. It features a structured Controller-Service-Model architecture for maintainability and scalability.

## Architecture

The project follows a layered architecture inspired by Node.js patterns:

*   **Controllers**: Handle Discord interactions and response formatting.
*   **Services**: Contain business logic and cross-component orchestration.
*   **Models**: Manage database interactions (Repository pattern).
*   **Routes (Cogs)**: Define command entry points.

## Features

### Attendance
*   **Mark Attendance**: Users can mark themselves as "Present" or "Half Day".
*   **Late Policy**: "Present" status is only allowed within a configurable window (e.g., 9:00 AM - 9:15 AM). Late users must mark "Half Day" or "Absent".
*   **Status Tracking**: Supports tracking specific statuses like lunch breaks and "away" (AFK) periods.
*   **Auto-Drop**: Automatically ends the day for users at a configured time (e.g., 22:00 IST) and logs it.
*   **Auto-Absent**: Automatically marks users as "Absent" if they haven't marked attendance by the end of the day.

### Voice Tracking
*   **Session Logging**: Automatically tracks time spent in voice channels.
*   **Auto-Disconnect**: If a user signs out (`/drop`) while in a voice channel, their session is automatically split. Subsequent time is logged as "overtime".
*   **Detailed Stats**: Exports data with `hh:mm` formatting for Voice and Overtime, plus a Total Minutes column.

### Export (Google Sheets & CSV)
*   **Split Sheets**: Data is exported into two separate tabs per year:
    *   **{Year} Attendance**: Simplified status view.
    *   **{Year} Voice Stats**: Detailed voice metrics.
*   **CSV Download**: The `/csv` command returns two separate CSV files (Attendance and Voice Stats).

### General
*   **Persistent Responses**: All bot responses are visible to everyone (not ephemeral) for transparency.
*   **Channel Restriction**: Bot commands are restricted to a specific channel (default `#attendance`).
*   **Auto-Reply**: Automatically replies to mentions of absent or busy users.

## Setup

1.  **Prerequisites**:
    *   Python 3.8+
    *   MongoDB instance
    *   Google Service Account (if using Sheets export)

2.  **Installation**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configuration**:
    Create a `.env` file in the root directory:
    ```env
    # Credentials
    DISCORD_TOKEN=your_token
    MONGODB_URI=your_mongo_uri
    GOOGLE_CREDENTIALS_JSON=service_account.json
    GOOGLE_SHEET_ID=your_sheet_id
    
    # Guild & Channel
    TARGET_GUILD_ID=your_guild_id
    ATTENDANCE_CHANNEL_NAME=attendance
    
    # Time Rules (IST)
    ATTENDANCE_START_TIME=09:00
    LATE_LIMIT_MINUTES=15
    ATTENDANCE_END_TIME=22:00
    ATTENDANCE_AUTO_ABSENT_TIME=23:30
    ATTENDANCE_EXPORT_TIME=00:30
    ```

4.  **Running the Bot**:
    ```bash
    python main.py
    ```

### Google Sheets Setup

To enable export functionality, you need a Google Service Account:

1.  **Go to Google Cloud Console**: [https://console.cloud.google.com/](https://console.cloud.google.com/)
2.  **Create a Project** (if you haven't already).
3.  Search for **"Service Accounts"** in the top search bar and click it (under IAM & Admin).
4.  Click **+ CREATE SERVICE ACCOUNT** at the top.
    *   Give it a name (e.g., `discord-bot`).
    *   Click **Create and Continue**.
    *   (Optional) Grant it the **Editor** role so it can edit sheets.
    *   Click **Done**.
5.  Click on the email address of the service account you just created.
6.  Go to the **KEYS** tab (top menu).
7.  Click **ADD KEY** > **Create new key**.
8.  Select **JSON** and click **CREATE**.
    *   This will download a file to your computer.
9.  Rename that file to `service_account.json`.
10. Move it into your project folder.
11. Update your `.env` to say: `GOOGLE_CREDENTIALS_JSON=service_account.json`
12. **Final Critical Step**: Open your Service Account JSON file, copy the `client_email` address inside it, and **Share your Google Sheet with that email** (just like you share with a person).

## Commands

**Note**: All commands must be used in the configured `#attendance` channel.

### Attendance
*   `/attendance [status] [date] [reason]`: Mark Present (with time limit), Half Day, or Absent.
*   `/lunch`: Start lunch break.
*   `/resume`: Resume work (end lunch or away status).
*   `/away [reason]`: Set status to Away.
*   `/drop`: End the work day (Sign out).

### Statistics
*   `/today [user]`: View daily stats for a specific user.

### Export
*   `/csv [start] [end]`: Download Activity Report (Returns 2 CSV files).

### Utility
*   `/bhai-count [user]`: Check how many times a user has been called "bhai".

## Note from Developer

This project was built for fun and for internal use at [Snapsec](https://snapsec.co/). As a primarily Node.js developer, I may not have followed standard Python nuances or best practices (e.g., project structure, strict type hinting).

**Security Notice**:
This bot is designed for a single trusted server. It lacks advanced security features like **rate limiting** or **strict permission checks**. If you plan to scale this to multiple servers, consider improving:
*   **Permissions**: During development, I enabled **Administrator** permissions for convenience. This is **not recommended** for production. You should restrict the bot to only necessary permissions (e.g., `Manage Channels`, `Read/Send Messages`) via the Discord Developer Portal.
*   **Security**: Add `cooldowns` to commands and validate user permissions strictly.
*   **Structure**: Implement dependency injection and strict typing (`mypy`).

**Configuration Limitations**:
Many values are currently hardcoded in `.env` for simplicity, whereas a production-ready bot would configure these via Discord commands stored in a database.
*   **Hardcoded Values**: `ATTENDANCE_START_TIME`, `LATE_LIMIT_MINUTES`, `ATTENDANCE_END_TIME`, `ATTENDANCE_CHANNEL_NAME`, `TARGET_GUILD_ID`.
*   **Improvement**: It would be significantly better to manage these via **Server Role Permissions** and slashed commands (e.g., `/config set-channel #attendance`), allowing server admins to configure the bot without accessing the server filesystem.

## License & Usage

This project is **Open Source** and available for anyone to use. You are free to modify, distribute, and adapt the code for your needs, provided it is used for **ethical purposes**.

I encourage contribution and customization to fit your community's requirements. Happy coding!
