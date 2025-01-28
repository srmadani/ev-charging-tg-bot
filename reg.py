# reg.py
import sqlite3
import datetime
from telegram import Update
from telegram.ext import ContextTypes

DATABASE_NAME = "bot_database.db"  # Name of your SQLite database file

def initialize_database():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            battery_capacity TEXT,
            charging_rate TEXT,
            departure_time TEXT
        )
    """)

    # Create conversations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            start_time DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Create messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
            sender_type TEXT, -- 'user' or 'llm'
            message_text TEXT,
            message_time DATETIME,
            FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
        )
    """)

    conn.commit()
    conn.close()

initialize_database() # Initialize database on module import


async def is_user_registered(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user is not None

async def get_user_conversation_id(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT conversation_id FROM conversations WHERE user_id = ? ORDER BY start_time DESC LIMIT 1", (user_id,))
    conversation = cursor.fetchone()
    conn.close()
    if conversation:
        return conversation[0]
    return None # No conversation found


async def start_new_conversation(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    now = datetime.datetime.now()
    cursor.execute("INSERT INTO conversations (user_id, start_time) VALUES (?, ?)", (user_id, now))
    conn.commit()
    conversation_id = cursor.lastrowid
    conn.close()
    return conversation_id


async def store_user_info(user_id, battery_capacity, charging_rate, departure_time):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, battery_capacity, charging_rate, departure_time)
        VALUES (?, ?, ?, ?)
    """, (user_id, battery_capacity, charging_rate, departure_time))
    conn.commit()
    conn.close()


async def get_user_info(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT battery_capacity, charging_rate, departure_time FROM users WHERE user_id = ?", (user_id,))
    user_info = cursor.fetchone()
    conn.close()
    if user_info:
        return {
            "battery_capacity": user_info[0],
            "charging_rate": user_info[1],
            "departure_time": user_info[2]
        }
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and handles new user registration on /start command."""
    user = update.effective_user
    user_id = user.id

    if not await is_user_registered(user_id):
        context.user_data['registration_step'] = 'battery_capacity'
        await update.message.reply_html(
            rf"Hi {user.mention_html()}! Welcome! You are a new user. Let's get you set up. "
            "Please answer the following questions.\n\n"
            "What is your EV battery capacity (in kWh)? (e.g., 60 kWh)"
        )
    else:
        await update.message.reply_html(
            rf"Hi {user.mention_html()}! Welcome back! Send me a message to chat!"
        )


async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Starts the edit process to update user information."""
    user = update.effective_user
    user_id = user.id

    if await is_user_registered(user_id):
        context.user_data['registration_step'] = 'battery_capacity_edit'
        await update.message.reply_text(
            "Let's edit your information. Please answer the following questions again.\n\n"
            "What is your EV battery capacity (in kWh)? (e.g., 60 kWh)"
        )
    else:
        await update.message.reply_text(
            "You are not registered yet. Please use /start to register first."
        )


async def handle_registration_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles user responses during registration and edit process."""
    user_id = update.effective_user.id
    user_response = update.message.text

    step = context.user_data.get('registration_step')

    if step == 'battery_capacity' or step == 'battery_capacity_edit':
        context.user_data['battery_capacity_temp'] = user_response # Store temporarily in context
        await update.message.reply_text("What is your EV charging rate (in kW)? (e.g., 7 kW)")
        context.user_data['registration_step'] = 'charging_rate' if step == 'battery_capacity' else 'charging_rate_edit'
    elif step == 'charging_rate' or step == 'charging_rate_edit':
        context.user_data['charging_rate_temp'] = user_response # Store temporarily in context
        await update.message.reply_text("What is your preferred departure time? (e.g., 8:00 AM)")
        context.user_data['registration_step'] = 'departure_time' if step == 'charging_rate' else 'departure_time_edit'
    elif step == 'departure_time' or step == 'departure_time_edit':
        departure_time = user_response
        battery_capacity = context.user_data.get('battery_capacity_temp')
        charging_rate = context.user_data.get('charging_rate_temp')

        await store_user_info(user_id, battery_capacity, charging_rate, departure_time) # Store in DB

        if step == 'departure_time':
            await update.message.reply_text("Registration complete! You can now chat with the bot. you can always use /edit to update your information.")
        else: # step == 'departure_time_edit'
            await update.message.reply_text("Your information has been updated.")

        context.user_data.pop('registration_step', None) # Clear registration step
        context.user_data.pop('battery_capacity_temp', None) # Clear temp data
        context.user_data.pop('charging_rate_temp', None) # Clear temp data
    else:
        return # Not a registration response


async def is_registration_ongoing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks if registration is currently ongoing for the user.
    """
    return 'registration_step' in context.user_data

async def get_user_data_db(user_id): # Function to retrieve user data from db for debugging
    return await get_user_info(user_id)