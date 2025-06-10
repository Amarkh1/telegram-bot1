from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Start command received")
    await update.message.reply_text("Hello! This is a test bot.")

async def healthcheck(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Healthcheck received")
    await update.message.reply_text("Bot is running!")

def main():
    # Get token
    token = os.getenv("TELEGRAM_TOKEN")
    port = int(os.environ.get('PORT', 8000))
    
    # Get webhook domain
    domain = os.getenv('RAILWAY_PUBLIC_DOMAIN', 'telegram-bot1-production.up.railway.app')
    webhook_url = f"https://{domain}"
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Add simple handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("healthcheck", healthcheck))
    
    # Start webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url=webhook_url
    )

if __name__ == "__main__":
    main()
