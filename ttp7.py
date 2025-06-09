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
import pyttsx3
import re
from fuzzywuzzy import fuzz
import json
from datetime import datetime
import logging
import random

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize the text-to-speech engine
try:
    engine = pyttsx3.init()
except Exception as e:
    logger.warning(f"TTS initialization failed: {e}. TTS features will be disabled.")
    engine = None

# Set the correct FFmpeg path for Railway
FFMPEG_PATH = "ffmpeg"  # Railway should have ffmpeg available

# Function to convert .ogg to .wav
def convert_ogg_to_wav(input_file, output_file):
    input_file = os.path.abspath(input_file)
    output_file = os.path.abspath(output_file)
    command = f'"{FFMPEG_PATH}" -y -i "{input_file}" "{output_file}"'
    try:
        subprocess.run(command, shell=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e}")
        return False
    except FileNotFoundError:
        logger.error(f"FFmpeg executable not found at: {FFMPEG_PATH}")
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
        
        # Special handling for questions that require a flexible answer
        if "i am from" in expected_answer or "my name is" in expected_answer:
            if expected_answer in user_response:
                return True
        
        similarity_ratio = fuzz.ratio(user_response, expected_answer)
        if similarity_ratio >= 75:  # Lower threshold for more flexibility
            return True
        
        # Check if expected answer words are contained in user response
        expected_words = set(expected_answer.split())
        user_words = set(user_response.split())
        common_words = expected_words.intersection(user_words)
        
        # If most of the expected words are in the user's response
        if len(common_words) >= len(expected_words) * 0.7:
            return True
    
    return False

# Function to convert voice message to text
async def voice_to_text(voice_file):
    wav_file = os.path.join(os.getcwd(), "user_voice.wav")
    
    if not convert_ogg_to_wav(voice_file, wav_file):
        return None
        
    if not os.path.exists(wav_file):
        logger.error(f"Error: .wav file not found at {wav_file}")
        return None
    
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(wav_file) as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio)
            return text.lower()
    except sr.UnknownValueError:
        logger.info("Speech recognition could not understand the audio.")
        return None
    except sr.RequestError:
        logger.error("Speech recognition service failed.")
        return None
    finally:
        if os.path.exists(wav_file):
            os.remove(wav_file)

# Get token from environment variable
TOKEN = os.getenv('TELEGRAM_TOKEN')

if not TOKEN:
    logger.error("TELEGRAM_TOKEN environment variable not set!")
    exit(1)

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
        ],
        "current_question": 0
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
        "current_pair": 0,
        "answers": {
            "A": ["4"],
            "B": ["5"],
            "C": ["3"],
            "D": ["1"],
            "E": ["2"]
        }
    },
    "exercise3": {
        "title": "Exercise 3: Verb Identification",
        "instruction": "Find all the verbs in Exercise 2 and say what's similar.",
        "answers": ["All verbs are in the past simple form."],
        "verbs": ["cooked", "cleaned", "walked", "played", "listened", 
                 "danced", "cried", "called", "travelled", "visited"],
        "current_verb": 0,
    },
    "exercise4": {
        "title": "Exercise 4: Pronunciation Practice",
        "instruction": "Listen to the recording and repeat the sentences.",
        "audio_link": "https://youtu.be/KXadJTf1UFo",
        "sentences": [
            "We cooked dinner and we cleaned the house.",
            "I walked in the park and I played basketball.",
            "We listened to music and we danced.",
            "The baby cried so I called the doctor.",
            "I travelled by train and I visited a friend."
        ],
        "current_sentence": 0
    },
    "exercise5": {
        "title": "Exercise 5: Past Simple Rules",
        "instruction": "Complete the rules with verbs from Exercise 2.",
        "rules": {
            "A": "Add '-ed' to the verb (work → worked): ______",
            "B": "If verb ends with 'e', add '-d' (live → lived): ______",
            "C": "Consonant + 'y' → '-ied' (study → studied): ______",
            "D": "Vowel + 'y' → '-ed' (enjoy → enjoyed): ______",
            "E": "Double consonant + '-ed' (stop → stopped): ______"
        },
        "current_rule": 0,
        "answers": {
            "A": ["cooked", "cleaned", "walked", "played", "listened"],
            "B": ["danced", "liked"],
            "C": ["cried", "tried"],
            "D": ["played", "enjoyed"],
            "E": ["stopped", "planned"]
        }
    },
    "exercise6": {
        "title": "Exercise 6: Verb Conjugation",
        "instruction": "Complete with past form of verbs in the box.",
        "verbs": ["love", "play", "stop", "study", "talk", "visit", "watch"],
        "questions": [
            "I ______ TV with my brother last week.",
            "My friends and I ______ for the exam last month.",
            "On Tuesday, they ______ to their boss about the holiday.",
            "She ______ the guitar yesterday.",
            "The man ______ the car at the red light.",
            "They ______ her new book because it was very funny.",
            "We ______ three museums when we were in London."
        ],
        "answers": [
            ["watched"],
            ["studied"],
            ["talked"],
            ["played"],
            ["stopped"],
            ["loved"],
            ["visited"]
        ],
        "current_question": 0
    },
    "exercise7": {
        "title": "Exercise 7: Picture Prediction",
        "instruction": "Look at Susan's pictures and guess her activities.",
        "examples": ["Maybe Susan baked a cake.", "Maybe Susan played tennis."],
        "current_prediction": 0
    },
    "exercise8": {
        "title": "Exercise 8: Reading Comprehension",
        "text": """Yesterday was Saturday and my family and I had a really fun day. It was my sister's birthday so my partner, Martin, my son, Luca and I visited her in the morning. She was very happy and she loved her present - a new book by her favourite author. My sister likes reading very much!

In the afternoon, Luca and I played tennis together. He usually plays football but he likes tennis, too. Then, Martin and I cooked dinner. I was happy because we don't often cook together. We also called my dad, who lives in Canada. He really likes living there. In the evening, my family and I watched a film together. We rarely watch films together so it was great!""",
        "questions": [
            "Whose birthday was it?",
            "What present did Susan's sister get?",
            "What sports does Luca usually play?",
            "Why was Susan happy about cooking dinner?",
            "Where does Susan's dad live?"
        ],
        "answers": [
            ["Susan's sister", "her sister"],
            ["a new book", "book"],
            ["football", "soccer"],
            ["they don't often cook together", "rarely cook together"],
            ["Canada"]
        ],
        "current_question": 0
    },
    "exercise9": {
        "title": "Exercise 9: Present vs Past",
        "instruction": "Say two things about each person: one present, one past.",
        "people": {
            "Luca": {
                "present": ["usually plays football", "likes tennis"],
                "past": ["played tennis with Susan", "visited aunt"]
            },
            "Martin": {
                "present": ["partner", "lives with Susan"],
                "past": ["cooked dinner", "visited sister"]
            },
            "Susan's dad": {
                "present": ["lives in Canada", "likes living there"],
                "past": ["was called"]
            },
            "Susan": {
                "present": ["has a family", "has a son"],
                "past": ["watched a film", "played tennis", "cooked dinner"]
            }
        },
        "current_person": 0
    },
    "exercise10": {
        "title": "Exercise 10: Personal Practice",
        "instruction": "Talk about what you/people did yesterday/last week/month.",
        "verbs": ["call", "email", "travel", "clean", "listen", "visit", "cook", 
                "play", "walk", "cry", "study", "watch", "dance", "talk", "work"],
        "examples": [
            "Yesterday, I cried when I watched a YouTube video with three dogs.",
            "Last week, my friends and I listened to music and walked in the park.",
            "Last month, my colleagues travelled to London and talked to clients."
        ],
        "current_example": 0
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
    context.user_data['current_exercise'] = 1
    return await start_exercise(update, context, 1)

# Enhanced voice message handler
async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    file_id = voice.file_id
    logger.info(f"Voice message received! File ID: {file_id}")
    
    try:
        # Download the voice file
        file = await voice.get_file()
        file_path = os.path.join(os.getcwd(), "user_voice.ogg")
        await file.download_to_drive(file_path)
        
        # Convert voice to text
        text = await voice_to_text(file_path)
        
        if text:
            await update.message.reply_text(f"Recognized text: {text}")
            # Now handle the recognized text as a regular message
            update.message.text = text
            return await handle_exercise(update, context)
        else:
            await update.message.reply_text("Sorry, I could not understand the audio. Please try again or type your answer.")
    
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        await update.message.reply_text("Sorry, there was an error processing your voice message. Please type your answer.")
    
    finally:
        # Clean up files
        for file_path in ["user_voice.ogg", "user_voice.wav"]:
            if os.path.exists(file_path):
                os.remove(file_path)
    
    # Return current state to stay in the same exercise
    return context.user_data.get('current_exercise', EXERCISE1)

# Enhanced exercise handler with voice support
async def handle_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    exercise_number = context.user_data.get('current_exercise', 1)
    exercise_data = PAST_SIMPLE_WORKSHEET[f'exercise{exercise_number}']
    
    # Handle voice messages first
    if update.message.voice:
        return await handle_voice_message(update, context)
    
    # Handle text messages
    if update.message.text:
        user_input = update.message.text.strip().lower()
        
        # Check if user wants to skip (for pronunciation exercises)
        if user_input == 'skip' and exercise_number in [4]:
            context.user_data[f'exercise{exercise_number}']['current_item'] += 1
            await update.message.reply_text("Skipped to next item.")
            return await start_exercise(update, context, exercise_number)
        
        # Process answer based on exercise type
        if exercise_number in [1, 6, 8]:
            # Get correct answers for current question
            current_item = context.user_data[f'exercise{exercise_number}']['current_item']
            expected_answers = exercise_data['answers'][current_item]
            
            # Check if answer is correct
            if is_response_correct(user_input, expected_answers):
                context.user_data[f'exercise{exercise_number}']['score'] += 1
                feedback = random.choice([
                    "✅ Great job! Your answer is correct! 🎉",
                    "✅ Excellent! You got it right! 👏",
                    "✅ Perfect! That's the correct answer! 🌟",
                    "✅ Well done! You're learning fast! 💪",
                    "✅ Fantastic! Keep up the good work! 🏆"
                ])
                
                # Move to next question
                context.user_data[f'exercise{exercise_number}']['current_item'] += 1
                total_items = len(exercise_data['questions'])
                
                if context.user_data[f'exercise{exercise_number}']['current_item'] < total_items:
                    feedback += f"\n\nQuestion {context.user_data[f'exercise{exercise_number}']['current_item'] + 1}: {exercise_data['questions'][context.user_data[f'exercise{exercise_number}']['current_item']]}"
                    await update.message.reply_text(feedback)
                    return exercise_number
                else:
                    feedback += f"\n\n🎉 You completed this exercise with {context.user_data[f'exercise{exercise_number}']['score']}/{total_items} correct answers!"
                    keyboard = get_navigation_keyboard(exercise_number)
                    await update.message.reply_text(feedback, reply_markup=keyboard)
                    return exercise_number
            else:
                feedback = random.choice([
                    "❌ Almost there! Try again.",
                    "❌ Not quite right. Let's try once more.",
                    f"❌ Good effort! The correct answer is: {expected_answers[0]}",
                    "❌ You're close! Think about it again."
                ])
                await update.message.reply_text(feedback)
                return exercise_number
        
        # Handle other exercises with simpler logic
        elif exercise_number == 4:  # Pronunciation practice
            current_sentence = context.user_data['exercise4']['current_sentence']
            target_sentence = exercise_data['sentences'][current_sentence].lower()
            similarity = fuzz.ratio(user_input, target_sentence)
            
            if similarity >= 80:
                feedback = "✅ Excellent! Your pronunciation is very accurate! 🎉"
            elif similarity >= 60:
                feedback = "✅ Good job! Your pronunciation is mostly correct! 👍"
            else:
                feedback = "❌ Try again. Listen to the example and repeat."
            
            feedback += f"\n\nSimilarity score: {similarity}%"
            await update.message.reply_text(feedback)
            
            # Move to next sentence if similarity is good enough
            if similarity >= 60:
                context.user_data['exercise4']['current_sentence'] += 1
                if context.user_data['exercise4']['current_sentence'] < len(exercise_data['sentences']):
                    await update.message.reply_text("Moving to next sentence...")
                    return await start_exercise(update, context, exercise_number)
                else:
                    await update.message.reply_text("🎉 You completed all pronunciation exercises!")
                    keyboard = get_navigation_keyboard(exercise_number)
                    await update.message.reply_text("Choose what to do next:", reply_markup=keyboard)
                    return exercise_number
            return exercise_number
        
        else:
            # Simple acknowledgment for other exercises
            await update.message.reply_text("Great! Your answer has been recorded. 👍")
            keyboard = get_navigation_keyboard(exercise_number)
            await update.message.reply_text("What would you like to do next?", reply_markup=keyboard)
            return exercise_number
    
    await update.message.reply_text("Please send a text or voice message to continue.")
    return exercise_number

# Start a specific exercise
async def start_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE, exercise_number: int):
    exercise_name = f"exercise{exercise_number}"
    exercise_data = PAST_SIMPLE_WORKSHEET[exercise_name]
    
    # Initialize exercise data
    if exercise_name not in context.user_data:
        context.user_data[exercise_name] = {"current_item": 0, "score": 0}
    
    # Exercise-specific content
    if exercise_number == 1:
        current_q = context.user_data['exercise1']['current_item']
        content = (
            f"{exercise_data['title']}\n\n"
            f"Examples:\n{exercise_data['examples'][0]}\n{exercise_data['examples'][1]}\n\n"
            f"{exercise_data['instruction']}\n\n"
            f"Question {current_q + 1}: {exercise_data['questions'][current_q]}"
        )
    elif exercise_number == 2:
        pairs = "\n".join([f"{person}: {sentence}" for person, sentence in exercise_data['pairs'].items()])
        content = (
            f"{exercise_data['title']}\n\n"
            f"{exercise_data['instruction']}\n\n"
            f"People:\n{pairs}\n\n"
            "Type your matches like: 'A-4, B-5, C-3, D-1, E-2'"
        )
    elif exercise_number == 3:
        content = (
            f"{exercise_data['title']}\n\n"
            f"{exercise_data['instruction']}\n\n"
            "Look back at Exercise 2 and find all the verbs (action words).\n"
            "What do you notice about all these verbs?"
        )
    elif exercise_number == 4:
        current_sentence = context.user_data['exercise4']['current_sentence']
        sentence = exercise_data['sentences'][current_sentence]
        
        content = (
            f"{exercise_data['title']}\n\n"
            f"{exercise_data['instruction']}\n\n"
            f"🎯 Sentence {current_sentence + 1}: {sentence}\n\n"
            "📱 Send a voice message to practice pronunciation!\n"
            "💬 Or type the sentence if you prefer\n"
            "⏭️ Type 'skip' to move to the next sentence"
        )
        
        # Try to generate and send audio
        try:
            audio_file = f"tts_sentence_{current_sentence}.wav"
            if text_to_speech(sentence, audio_file):
                nav_keyboard = get_navigation_keyboard(exercise_number)
                
                if hasattr(update, 'callback_query') and update.callback_query:
                    with open(audio_file, 'rb') as audio:
                        await update.callback_query.message.reply_audio(audio=audio)
                    await update.callback_query.message.reply_text(content, reply_markup=nav_keyboard)
                else:
                    with open(audio_file, 'rb') as audio:
                        await update.message.reply_audio(audio=audio)
                    await update.message.reply_text(content, reply_markup=nav_keyboard)
                os.remove(audio_file)  # Clean up
                return globals()[f"EXERCISE{exercise_number}"]
        except Exception as e:
            logger.error(f"TTS Error: {e}")
    
    elif exercise_number == 5:
        rules_text = "\n".join([f"{letter}. {rule}" for letter, rule in exercise_data['rules'].items()])
        content = (
            f"{exercise_data['title']}\n\n"
            f"{exercise_data['instruction']}\n\n"
            f"{rules_text}\n\n"
            "Give examples for each rule using verbs from Exercise 2."
        )
    elif exercise_number == 6:
        current_q = context.user_data['exercise6']['current_item']
        content = (
            f"{exercise_data['title']}\n\n"
            f"Available verbs: {', '.join(exercise_data['verbs'])}\n\n"
            f"{exercise_data['instruction']}\n\n"
            f"Question {current_q + 1}: {exercise_data['questions'][current_q]}"
        )
    elif exercise_number == 7:
        content = (
            f"{exercise_data['title']}\n\n"
            f"Examples:\n• {exercise_data['examples'][0]}\n• {exercise_data['examples'][1]}\n\n"
            f"{exercise_data['instruction']}\n\n"
            "What do you think Susan did? Start with 'Maybe Susan...'"
        )
    elif exercise_number == 8:
        current_q = context.user_data['exercise8']['current_item']
        content = (
            f"{exercise_data['title']}\n\n"
            f"Read this text:\n\n{exercise_data['text']}\n\n"
            f"Question {current_q + 1}: {exercise_data['questions'][current_q]}"
        )
    elif exercise_number == 9:
        people = list(exercise_data['people'].keys())
        content = (
            f"{exercise_data['title']}\n\n"
            f"Example for Susan's sister:\n"
            "Present: She likes reading.\n"
            "Past: She loved her present.\n\n"
            f"{exercise_data['instruction']}\n\n"
            f"Start with: {people[0]}\n"
            "Write one present tense and one past tense sentence."
        )
    elif exercise_number == 10:
        content = (
            f"{exercise_data['title']}\n\n"
            f"Use these verbs: {', '.join(exercise_data['verbs'])}\n\n"
            f"Examples:\n"
            f"• {exercise_data['examples'][0]}\n"
            f"• {exercise_data['examples'][1]}\n"
            f"• {exercise_data['examples'][2]}\n\n"
            f"{exercise_data['instruction']}\n\n"
            "Write your first sentence:"
        )
    
    # Always show navigation keyboard
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
            await query.edit_message_text(
                "Congratulations! You've completed all exercises!\n\n"
                "Use /start to begin again."
            )
            return ConversationHandler.END
        return await start_exercise(update, context, exercise_number)
    else:
        exercise_number = context.user_data.get('current_exercise', 1)
        return await start_exercise(update, context, exercise_number)

# Update the conversation handler to include voice support
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start_worksheet)],
    states={
        EXERCISE1: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE & ~filters.COMMAND, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE2: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE & ~filters.COMMAND, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE3: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE & ~filters.COMMAND, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE4: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE & ~filters.COMMAND, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE5: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE & ~filters.COMMAND, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE6: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE & ~filters.COMMAND, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE7: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE & ~filters.COMMAND, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE8: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE & ~filters.COMMAND, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE9: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE & ~filters.COMMAND, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
        EXERCISE10: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_exercise),
            MessageHandler(filters.VOICE & ~filters.COMMAND, handle_exercise),
            CallbackQueryHandler(navigate_exercises, pattern="^nav_")
        ],
    },
    fallbacks=[CommandHandler('cancel', lambda update, context: ConversationHandler.END)],
    per_message=False
)

def main():
    # Get port from environment or default to 8000
    PORT = int(os.environ.get('PORT', 8000))
    
    application = Application.builder().token(TOKEN).build()
    application.add_handler(conv_handler)
    
    # Add a separate voice handler for cases outside conversation
    application.add_handler(MessageHandler(filters.VOICE, handle_voice_message))
    
    logger.info("Past Simple Worksheet Bot started with voice support!")
    
    # For Railway deployment, use webhook mode
    if os.getenv('RAILWAY_ENVIRONMENT'):
        # Railway deployment
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN', 'your-app.railway.app')}"
        )
    else:
        # Local development
        application.run_polling()

if __name__ == "__main__":
    main()
