# main.py
import os
from dotenv import load_dotenv
load_dotenv()
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta
from data_processing.training import get_forecasts

from reg import (
    start, edit, handle_registration_response, is_registration_ongoing,
    get_user_data_db, process_charging_input, get_user_info, send_welcome_back_message,
    is_user_registered
)
from llm import get_llm_response
from pred import pred

from retrieve_data import get_data

def format_forecast_message(forecasts, hours_to_charge) -> str:
    """
    Formats the forecast vectors into a readable message.
    forecasts is a 2*(n-3) vector [cost_reductions, emission_reductions]
    """
    cost_reductions = forecasts[:len(forecasts)//2]
    emission_reductions = forecasts[len(forecasts)//2:]
    
    # Calculate hours and minutes more precisely
    hours = int(hours_to_charge)
    minutes = int((hours_to_charge - hours) * 60)
    
    message = f"It will take {hours} hours and {minutes} minutes to charge your EV.\n\n"
    message += "Here are your potential savings if you start charging at different times:\n\n"
    message += "```\nStart Time  Cost Savings  CO2 Savings\n"
    message += "------------------------------------\n"
    
    current_time = datetime.now()
    # Keep current minutes for more accurate time display
    current_minutes = current_time.minute
    
    for i, (cost, emission) in enumerate(zip(cost_reductions, emission_reductions)):
        # Calculate future time keeping original minutes
        future_time = current_time + timedelta(hours=i)
        time_str = future_time.strftime("%I:%M %p")
        message += f"{time_str}    ${cost:6.2f}    {emission:6.1f} g\n"
    
    message += "```"
    return message

async def handle_charging_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles user input for charging state and departure time."""
    try:
        # Get SoC and departure time from user input
        soc, departure_time = await process_charging_input(update.message.text)
        
        # Get user's default departure time if none provided
        user_info = await get_user_info(update.effective_user.id)
        if departure_time is None:
            departure_time = user_info['departure_time']
        
        # Get user's charging parameters from database
        battery_capacity = user_info['battery_capacity']
        charging_rate = user_info['charging_rate']
        
        # Convert departure time to datetime
        dt_str = departure_time
        dt = datetime.strptime(dt_str, "%I:%M %p")
        current_time = datetime.now()
        dt = dt.replace(year=current_time.year, month=current_time.month, day=current_time.day)
        
        # If departure time is earlier than current time, assume it's for tomorrow
        if dt < current_time:
            dt = dt + timedelta(days=1)
        
        # Get price and carbon intensity records for the past 24 hours
        emission_api_token = os.getenv("emission_api_token")
        carbon_intensity_vector,electricity_price_vector = get_data(emission_api_token)
        forecasted_24 = get_forecasts(electricity_price_vector, carbon_intensity_vector)

        # Get forecasts from prediction function
        forecasts, hours_to_charge = pred(soc, dt, battery_capacity, charging_rate, forecasted_24)
        
        # Format and send response
        await update.message.reply_text(
            f"Current Status:\n"
            f"• Battery Level: {soc}%\n"
            f"• Departure Time: {departure_time}\n"
            f"• Battery Capacity: {battery_capacity} kWh\n"
            f"• Charging Rate: {charging_rate} kW\n\n"
            "Analyzing optimal charging times..."
        )
        
        # Send formatted forecast message
        forecast_message = format_forecast_message(forecasts, hours_to_charge)
        await update.message.reply_text(
            forecast_message,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await update.message.reply_text(
            "I couldn't process that input. Please provide the state of charge percentage "
            "and optionally when you'll leave (e.g., 'Battery is at 45% and I'll leave at 9:30 AM' "
            "or just 'Battery is at 45%')\n\n"
            f"Error details: {str(e)}"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes messages to appropriate handlers based on registration status."""
    # First check if registration is ongoing
    if await is_registration_ongoing(update, context):
        await handle_registration_response(update, context)
        return

    # Check if user needs registration
    if not await is_user_registered(update.effective_user.id):
        context.user_data['registration_step'] = 'battery_capacity'
        await update.message.reply_html(
            rf"Hi {update.effective_user.mention_html()}! You need to register first.\n\n"
            "What is your EV battery capacity (in kWh)? (e.g., 60 kWh)"
        )
        return

    # Handle charging input
    await handle_charging_input(update, context)

async def debug_get_user_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug command to get user data from db."""
    user_id = update.effective_user.id
    user_data = await get_user_data_db(user_id)
    await update.message.reply_text(f"User data from DB: {user_data}")

def main() -> None:
    """Run the telegram bot."""
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    application = ApplicationBuilder().token(telegram_bot_token).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("edit", edit))
    application.add_handler(CommandHandler("getuserdata", debug_get_user_data))

    # Message handler for text messages
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()