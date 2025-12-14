import os
import pytz
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Discord
TOKEN = os.getenv('DISCORD_TOKEN')

# Database
MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME', 'discord_activity')

# Timezone
IST = pytz.timezone('Asia/Kolkata')
