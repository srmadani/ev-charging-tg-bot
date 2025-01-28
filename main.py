# main.py
import os
from dotenv import load_dotenv
load_dotenv()
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Import functions from reg.py
from reg import start, edit, handle_registration_response, is_registration_ongoing, get_user_data_db # Import get_user_data_db for debugging

# Import function from llm.py
from llm import get_llm_response

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message and get LLM response."""
    user_message = update.message.text
    user_id = update.effective_user.id

    llm_response = await get_llm_response(user_message, str(user_id)) # Call async get_llm_response

    await update.message.reply_text(llm_response)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles all text messages and routes them to either registration handler or echo handler
    based on whether registration is ongoing.
    """
    if await is_registration_ongoing(update, context):
        await handle_registration_response(update, context)
    else:
        await echo(update, context)


async def debug_get_user_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: # Debug command
    """Debug command to get user data from db."""
    user_id = update.effective_user.id
    user_data = await get_user_data_db(user_id)
    await update.message.reply_text(f"User data from DB: {user_data}")


def main() -> None:
    """Run the telegram bot."""
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN") # Ensure TELEGRAM_BOT_TOKEN is in .env

    if not telegram_bot_token:
        print("Error: TELEGRAM_BOT_TOKEN not found in environment variables.")
        return

    application = ApplicationBuilder().token(telegram_bot_token).build()

    # Command handlers for registration and start
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("edit", edit))

    # Debug command to get user data
    application.add_handler(CommandHandler("getuserdata", debug_get_user_data)) # Add debug command

    # Message handler for ALL text messages (routes based on registration status)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()