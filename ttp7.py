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
    PORT = int(os.environ.get('PORT', 8000))
    RAILWAY_PUBLIC_DOMAIN = os.getenv('RAILWAY_PUBLIC_DOMAIN')
    if not RAILWAY_PUBLIC_DOMAIN:
        logger.warning("RAILWAY_PUBLIC_DOMAIN not found, using default domain")
        RAILWAY_PUBLIC_DOMAIN = "telegram-bot1-production.up.railway.app"
    
    # Don't add any port to the webhook URL!
    WEBHOOK_URL = f"https://{RAILWAY_PUBLIC_DOMAIN}"
    
    logger.info(f"Starting bot with webhook URL: {WEBHOOK_URL}")
    
    application = Application.builder().token(TOKEN).build()
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("debug", debug_command), group=-1)
    application.add_error_handler(error_handler)
    
    try:
        # Try with webhook
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL,
            drop_pending_updates=True
        )
        logger.info("Webhook started successfully")
    except Exception as e:
        logger.error(f"Error starting webhook: {str(e)}")
        logger.error(traceback.format_exc())
        logger.info("Falling back to polling mode...")
        application.run_polling(drop_pending_updates=True)
    
    
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
