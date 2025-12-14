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
*   **Status Tracking**: Supports tracking specific statuses like lunch breaks and "away" (AFK) periods.
*   **Daily Limits**: Enforces a single primary status (Present/Absent) per day.
*   **Absent Management**: Allows marking absence for the current day or future dates. Past dates are blocked.

### Voice Tracking
*   **Session Logging**: Automatically tracks time spent in voice channels.
*   **Auto-Disconnect**: If a user signs out (`/drop`) while in a voice channel, their session is automatically split. Subsequent time is logged as "overtime".
*   **Statistics**: Provides detailed activity stats per user or globally.
*   **Leaderboard**: Monthly leaderboard for voice activity.

### General
*   **Ephemeral Responses**: All bot responses are private (ephemeral) to keep channels clean.
*   **Auto-Reply**: Automatically replies to mentions of absent or busy users with their status and return date.
*   **Multi-Guild Support**: All data is scoped to specific servers (Guilds).

## Setup

1.  **Prerequisites**:
    *   Python 3.8+
    *   MongoDB instance

2.  **Installation**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configuration**:
    Create a `.env` file in the root directory:
    ```env
    DISCORD_TOKEN=your_token_here
    MONGO_URI=your_mongodb_connection_string
    DB_NAME=discord_activity
    ```

4.  **Running the Bot**:
    ```bash
    python main.py
    ```

## Commands

### Attendance
*   `/attendance [status]`: Mark attendance (Present, Half Day - Joining Late, Half Day - Leaving Early).
*   `/lunch`: Start lunch break.
*   `/resume`: Resume work (end lunch or away status).
*   `/away [reason]`: Set status to Away.
*   `/drop`: End the work day (Sign out).
*   `/absent [date] [reason]`: Mark yourself absent for today or a future date.

### Statistics
*   `/statistic [user] [date]`: View activity stats for a specific user or the entire server.
*   `/leaderboard [month]`: View the top users by voice duration for the month.

### Utility
*   `/bhai-count [user]`: Check how many times a user has been called "bhai".
*   `/cls [limit]`: Clear bot messages from the channel.
