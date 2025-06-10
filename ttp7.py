from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
import speech_recognition as sr
import os
import subprocess
import re
from fuzzywuzzy import fuzz
import json
from datetime import datetime
import logging
import random
import traceback
from telegram import __version__ as TG_VER

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize the text-to-speech engine with error handling
engine = None
try:
    import pyttsx3
    engine = pyttsx3.init()
    logger.info("TTS engine initialized successfully")
except Exception as e:
    logger.warning(f"TTS initialization failed: {e}. TTS features will be disabled.")

# Set the correct FFmpeg path for Railway
FFMPEG_PATH = "ffmpeg"

# Function to convert .ogg to .wav
def convert_ogg_to_wav(input_file, output_file):
    input_file = os.path.abspath(input_file)
    output_file = os.path.abspath(output_file)
    command = [FFMPEG_PATH, '-y', '-i', input_file, output_file]
    try:
        subprocess.run(command, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e}")
        return False
    except FileNotFoundError:
        logger.error(f"FFmpeg executable not found")
        return False

# Function to convert text to speech
def text_to_speech(text: str, output_file: str):
    if engine is None:
        logger.warning("TTS engine not available")
        return False
    try:
        engine.save_to_file(text, output_file)
        engine.runAndWait()
        return True
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return False

# Function to normalize text
def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# Function to check if the user's response matches the expected answer
def is_response_correct(user_response: str, expected_answers: list) -> bool:
    user_response = normalize_text(user_response)
    
    for expected_answer in expected_answers:
        expected_answer = normalize_text(expected_answer)
        
        similarity_ratio = fuzz.ratio(user_response, expected_answer)
        if similarity_ratio >= 75:
            return True
        
        # Check if expected answer words are contained in user response
        expected_words = set(expected_answer.split())
        user_words = set(user_response.split())
        common_words = expected_words.intersection(user_words)
        
        # If most of the expected words are in the user's response
        if len(common_words) >= len(expected_words) * 0.7:
            return True
    
    return False

# Get token from environment variable
TOKEN = os.getenv('TELEGRAM_TOKEN')

if not TOKEN:
    logger.error("TELEGRAM_TOKEN environment variable not set!")
    exit(1)
else:
    logger.info("TELEGRAM_TOKEN found successfully")

# Define conversation states for each exercise
EXERCISE1, EXERCISE2, EXERCISE3, EXERCISE4, EXERCISE5, EXERCISE6, EXERCISE7, EXERCISE8, EXERCISE9, EXERCISE10 = range(10)

# Define the worksheet content
PAST_SIMPLE_WORKSHEET = {
    "exercise1": {
        "title": "Exercise 1: Days and Months",
        "instruction": "Complete the gaps with days of the week and months.",
        "examples": [
            "Today is Sunday. Yesterday was Saturday.",
            "This month is August. Last month was July."
        ],
        "questions": [
            "Today is ______.",
            "This month is ______.",
            "Yesterday was ______.",
            "Last month was ______."
        ],
        "answers": [
            ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
            ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"],
            ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
            ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
        ]
    },
    "exercise2": {
        "title": "Exercise 2: Matching Activity",
        "instruction": "Match the people (A-E) with the sentences (1-5).",
        "pairs": {
            "Person A": "1.I walked in the park and I played basketball.",
            "Person B": "2.We cooked dinner and we cleaned the house.",
            "Person C": "3.I travelled by train and I visited a friend.",
            "Person D": "4.The baby cried so I called the doctor.",
            "Person E": "5.We listened to music and we danced.",
        },
        "answers": {
            "A": ["4"],
            "B": ["5"],
            "C": ["3"],
            "D": ["1"],
            "E": ["2"]
        }
    }
}

# Navigation keyboard
def get_navigation_keyboard(current_exercise):
    buttons = []
    if current_exercise > 1:
        buttons.append(InlineKeyboardButton("← Previous", callback_data=f"nav_{current_exercise-1}"))
    if current_exercise < 10:
        buttons.append(InlineKeyboardButton("Next →", callback_data=f"nav_{current_exercise+1}"))
    buttons.append(InlineKeyboardButton("Restart", callback_data="nav_1"))
    return InlineKeyboardMarkup([buttons])

# Start the worksheet
async def start_worksheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Start command received from {update.effective_user.id}")
    context.user_data['current_exercise'] = 1
    welcome_msg = (
        "🎓 Welcome to the Past Simple Worksheet Bot! 🎓\n\n"
        "This interactive bot will help you practice past simple tense through 10 exercises.\n"
        "You can type your answers or send voice messages! 🎤\n\n"
        "Let's start with Exercise 1..."
    )
    await update.message.reply_text(welcome_msg)
    return await start_exercise(update, context, 1)

# Enhanced exercise handler with voice support
async def handle_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    exercise_number = context.user_data.get('current_exercise', 1)
    
    logger.info(f"Handling exercise {exercise_number} for user {update.effective_user.id}")
    
    # Handle voice messages
    if update.message.voice:
        try:
            logger.info("Processing voice message")
            voice_file = await update.message.voice.get_file()
            voice_path = f"voice_{update.message.from_user.id}.ogg"
            wav_path = f"voice_{update.message.from_user.id}.wav"

            await voice_file.download_to_drive(voice_path)
            
            if not convert_ogg_to_wav(voice_path, wav_path):
                await update.message.reply_text("❌ Error converting audio file.")
                return exercise_number

            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio = recognizer.record(source)
                user_speech = recognizer.recognize_google(audio).lower()
                await update.message.reply_text(f"🎙️ I heard: '{user_speech}'")
                
                # Process as text
                update.message.text = user_speech
                return await handle_exercise(update, context)

        except sr.UnknownValueError:
            await update.message.reply_text("❌ Sorry, I couldn't understand the audio.")
            return exercise_number
        except Exception as e:
            logger.error(f"Voice processing error: {e}")
            await update.message.reply_text("❌ Error processing voice message.")
            return exercise_number
        finally:
            for path in [voice_path, wav_path]:
                try:
                    if 'path' in locals() and os.path.exists(path):
                        os.remove(path)
                except:
                    pass

    # Handle text messages
    elif update.message.text:
        user_input = update.message.text.strip().lower()
        logger.info(f"Processing text: {user_input}")
        
        if exercise_number == 1:
            # Initialize if needed
            if 'exercise1' not in context.user_data:
                context.user_data['exercise1'] = {"current_item": 0, "score": 0}
            
            current_item = context.user_data['exercise1']['current_item']
            expected_answers = PAST_SIMPLE_WORKSHEET['exercise1']['answers'][current_item]
            
            if is_response_correct(user_input, expected_answers):
                context.user_data['exercise1']['score'] += 1
                context.user_data['exercise1']['current_item'] += 1
                
                if context.user_data['exercise1']['current_item'] < 4:
                    next_q = context.user_data['exercise1']['current_item']
                    await update.message.reply_text(
                        f"✅ Correct! Next question: {PAST_SIMPLE_WORKSHEET['exercise1']['questions'][next_q]}"
                    )
                    return EXERCISE1
                else:
                    score = context.user_data['exercise1']['score']
                    await update.message.reply_text(
                        f"🎉 Exercise 1 completed! Score: {score}/4",
                        reply_markup=get_navigation_keyboard(1)
                    )
                    return EXERCISE1
            else:
                await update.message.reply_text(f"❌ Try again! Hint: {expected_answers[0]}")
                return EXERCISE1
                
        elif exercise_number == 2:
            # Handle Exercise 2 matching
            if not re.match(r'^([A-E]-[1-5],?\s*)+$', user_input.upper()):
                await update.message.reply_text("Please use format: 'A-4, B-5, C-3, D-1, E-2'")
                return EXERCISE2
            
            user_pairs = {}
            for pair in user_input.upper().split(','):
                pair = pair.strip()
                if '-' in pair:
                    k, v = pair.split('-', 1)
                    user_pairs[k.strip()] = v.strip()
            
            correct = 0
            for k, correct_list in PAST_SIMPLE_WORKSHEET['exercise2']['answers'].items():
                if user_pairs.get(k) in correct_list:
                    correct += 1
            
            await update.message.reply_text(
                f"You got {correct}/5 pairs correct!",
                reply_markup=get_navigation_keyboard(2)
            )
            return EXERCISE2
        
        else:
            # For other exercises, just acknowledge and show navigation
            await update.message.reply_text(
                "✅ Thank you for your answer!",
                reply_markup=get_navigation_keyboard(exercise_number)
            )
            return exercise_number

    else:
        await update.message.reply_text("Please send a text message or voice message.")
        return exercise_number

# Start a specific exercise
async def start_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE, exercise_number: int):
    logger.info(f"Starting exercise {exercise_number}")
    
    if exercise_number == 1:
        if 'exercise1' not in context.user_data:
            context.user_data['exercise1'] = {"current_item": 0, "score": 0}
        
        current_q = context.user_data['exercise1']['current_item']
        content = (
            f"📚 Exercise 1: Days and Months\n\n"
            f"📖 Examples:\n• Today is Sunday. Yesterday was Saturday.\n• This month is August. Last month was July.\n\n"
            f"📝 Complete the gaps with days of the week and months.\n\n"
            f"❓ Question {current_q + 1}: {PAST_SIMPLE_WORKSHEET['exercise1']['questions'][current_q]}"
        )
    elif exercise_number == 2:
        pairs = "\n".join([f"{person}: {sentence}" for person, sentence in PAST_SIMPLE_WORKSHEET['exercise2']['pairs'].items()])
        content = (
            f"📚 Exercise 2: Matching Activity\n\n"
            f"📝 Match the people (A-E) with the sentences (1-5).\n\n"
            f"👥 People and their activities:\n{pairs}\n\n"
            "💬 Type your matches like: 'A-4, B-5, C-3, D-1, E-2'"
        )
    else:
        content = f"📚 Exercise {exercise_number}\n\nThis exercise is under construction. Please use navigation buttons."
    
    nav_keyboard = get_navigation_keyboard(exercise_number)
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(content, reply_markup=nav_keyboard)
    else:
        await update.message.reply_text(content, reply_markup=nav_keyboard)
    
    return globals()[f"EXERCISE{exercise_number}"]

# Navigation handler
async def navigate_exercises(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query
        await query.answer()
        exercise_number = int(query.data.split('_')[1])
        context.user_data['current_exercise'] = exercise_number
        
        if exercise_number > 10:
            await query.edit_message_text("🎉 Congratulations! You've completed all exercises!")
            return ConversationHandler.END
            
        return await start_exercise(update, context, exercise_number)
    else:
        exercise_number = context.user_data.get('current_exercise', 1)
        return await start_exercise(update, context, exercise_number)

# Error handler
async def error_handler(update, context):
    logger.error(f"Exception while handling an update: {context.error}")
    logger.error(traceback.format_exc())

# Debug command handler
async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Debug: Bot is running! Version: {TG_VER}")

# Conversation handler
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start_worksheet)],
    states={
        EXERCISE1: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE2: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE3: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE4: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE5: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE6: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE7: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE8: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE9: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE10: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
    },
    fallbacks=[
        CommandHandler("cancel", lambda update, context: ConversationHandler.END),
        CommandHandler("start", start_worksheet)
    ],
    per_message=False
)

def main():
    PORT = int(os.environ.get('PORT', 8000))
    RAILWAY_PUBLIC_DOMAIN = os.getenv('RAILWAY_PUBLIC_DOMAIN')
    if not RAILWAY_PUBLIC_DOMAIN:
        RAILWAY_PUBLIC_DOMAIN = "telegram-bot1-production.up.railway.app"
    
    WEBHOOK_URL = f"https://{RAILWAY_PUBLIC_DOMAIN}"
    
    application = Application.builder().token(TOKEN).build()
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("debug", debug_command), group=-1)
    application.add_error_handler(error_handler)
    
    logger.info("Starting bot in webhook mode")
    logger.info(f"Webhook URL: {WEBHOOK_URL}")
    logger.info(f"Port: {PORT}")
    
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()
