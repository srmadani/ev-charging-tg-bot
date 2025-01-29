# reg.py
import sqlite3
import datetime
from telegram import Update
from telegram.ext import ContextTypes

DATABASE_NAME = "bot_database.db"

def initialize_database():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            battery_capacity REAL, 
            charging_rate REAL,
            departure_time TEXT 
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            start_time DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
            sender_type TEXT,
            message_text TEXT,
            message_time DATETIME,
            FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
        )
    """)

    conn.commit()
    conn.close()

initialize_database()

async def process_user_input(user_input: str, input_type: str) -> str:
    """Process user input using LLM to extract the required information."""
    prompts = {
        'battery_capacity': """
            Extract the battery capacity in kWh as a number from the following text. 
            Only return the numeric value without any units or additional text.
            If multiple numbers are present, identify the one that represents battery capacity.
            Example input: "my tesla has a 76.2kwh battery capacity"
            Expected output: 76.2
            
            User input: {input}
            """,
            
        'charging_rate': """
            Extract the charging rate in kW as a number from the following text.
            Only return the numeric value without any units or additional text.
            If multiple numbers are present, identify the one that represents charging rate.
            Example input: "it charges at 7.4kw at home"
            Expected output: 7.4
            
            User input: {input}
            """,
            
        'departure_time': """
            Extract the time in HH:MM AM/PM format from the following text.
            If the time format is different, convert it to HH:MM AM/PM.
            Only return the time without any additional text.
            Example input: "i leave at 8:30 in the morning"
            Expected output: 8:30 AM
            
            User input: {input}
            """
    }
    
    prompt = prompts[input_type].format(input=user_input)
    from llm import get_llm_response
    processed_value = await get_llm_response(prompt, "system")
    return processed_value.strip()

async def process_charging_input(user_input: str) -> tuple:
    """Process user input to extract SoC and optional departure time."""
    prompt = """
    Extract the state of charge (SoC) percentage and optional departure time from the following text.
    Return only two values separated by a comma: SoC number (without % symbol), departure time in HH:MM AM/PM format.
    If no departure time is mentioned, return 'None' for the second value.
    Example input: "battery is at 45% and I'll leave at 9:30 AM"
    Expected output: 45, 9:30 AM
    
    User input: {input}
    """.format(input=user_input)
    
    from llm import get_llm_response
    response = await get_llm_response(prompt, "system")
    soc, departure_time = response.strip().split(',')
    soc = float(soc.strip())
    departure_time = departure_time.strip()
    return soc, None if departure_time == 'None' else departure_time

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
    return conversation[0] if conversation else None

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

async def send_welcome_back_message(update: Update) -> None:
    """Sends the welcome back message asking for SoC and departure time."""
    await update.message.reply_text(
        "Welcome back home! Please let me know your EV's state of battery and when will you leave home? "
        "(e.g., 'Battery is at 45% and I'll leave at 9:30 AM' or just 'Battery is at 45%')\n\n"
        "You can also edit your saved information using /edit"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and handles new user registration."""
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
        await send_welcome_back_message(update)

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

    try:
        if step in ['battery_capacity', 'battery_capacity_edit']:
            processed_value = await process_user_input(user_response, 'battery_capacity')
            context.user_data['battery_capacity_temp'] = float(processed_value)
            await update.message.reply_text("What is your EV charging rate (in kW)? (e.g., 7 kW)")
            context.user_data['registration_step'] = 'charging_rate' if step == 'battery_capacity' else 'charging_rate_edit'
            
        elif step in ['charging_rate', 'charging_rate_edit']:
            processed_value = await process_user_input(user_response, 'charging_rate')
            context.user_data['charging_rate_temp'] = float(processed_value)
            await update.message.reply_text("What is your preferred departure time? (e.g., 8:00 AM)")
            context.user_data['registration_step'] = 'departure_time' if step == 'charging_rate' else 'departure_time_edit'
            
        elif step in ['departure_time', 'departure_time_edit']:
            processed_value = await process_user_input(user_response, 'departure_time')
            departure_time = processed_value
            battery_capacity = context.user_data.get('battery_capacity_temp')
            charging_rate = context.user_data.get('charging_rate_temp')

            await store_user_info(user_id, battery_capacity, charging_rate, departure_time)

            # Clear registration data
            context.user_data.pop('registration_step', None)
            context.user_data.pop('battery_capacity_temp', None)
            context.user_data.pop('charging_rate_temp', None)

            # Send welcome back message after registration/edit is complete
            await send_welcome_back_message(update)

    except ValueError as e:
        await update.message.reply_text("Sorry, I couldn't understand that input. Please try again with a valid number.")

async def is_registration_ongoing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Checks if registration is currently ongoing for the user."""
    return 'registration_step' in context.user_data

async def get_user_data_db(user_id):
    """Function to retrieve user data from db for debugging."""
    return await get_user_info(user_id)