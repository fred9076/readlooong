from typing import Final
import os
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict
import tempfile
import io
import re
import unicodedata

# Third-party imports
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image
import edge_tts
from paddleocr import PaddleOCR
import pytesseract
from dotenv import load_dotenv

# Constants and Configuration
load_dotenv()

TOKEN: Final = os.getenv('TELEGRAM_BOT_TOKEN')
BOT_USERNAME: Final = '@readlooong_bot'
LANGUAGE: Final = os.getenv('LANGUAGE')
VOICE: Final = os.getenv('VOICE')

MESSAGE_TIMEOUT = 10  # seconds to wait for additional messages
MAX_BUFFER_SIZE = 1000000  # maximum characters in buffer
MAX_PROCESSING_TIME = 30  # maximum seconds to process audio

# Global state
message_buffer = defaultdict(list)
last_message_time = defaultdict(datetime.now)
paddleocr = PaddleOCR(use_angle_cls=True, lang=LANGUAGE, use_gpu=False, show_log=False, use_space_char=True)

# Text processing utilities
def clean_eng_ocr_text(text: str) -> str:
    """Clean and normalize English OCR output text."""
    # Remove special character patterns
    text = re.sub(r'[!®°©]\s*', '', text)
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'\d+!l\d+!', '', text)
    text = re.sub(r'\(\d+\[\d+\]', '', text)
    text = re.sub(r'\d{1,2}:\d{1,2}(?::\d{1,2})?', '', text)
    
    # Replace single newlines with spaces
    text = re.sub(r'([^\n])\n([^\n])', r'\1 \2', text)
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    
    return text

def clean_chi_ocr_text(text: str) -> str:
    """Clean and normalize Chinese OCR output text."""
    if not text:
        return ""
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'\d{1,2}:\d{1,2}(?::\d{1,2})?', '', text)
    text = re.sub(r'\s+', '', text)
    return text.strip()

def is_chinese(text: str) -> bool:
    """Check if text is primarily Chinese."""
    chinese_chars = sum('\u4e00' <= char <= '\u9fff' for char in text)
    return chinese_chars > len(text) * 0.9

def create_safe_filename(text: str, max_length: int = 50) -> str:
    """Create a safe filename from text content."""
    safe_text = text[:max_length]
    safe_text = re.sub(r'[^a-zA-Z0-9\s-]', '', safe_text)
    safe_text = safe_text.strip().replace(' ', '_').lower()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{safe_text}_{timestamp}.mp3"

# Core functionality
async def download_photo(photo) -> bytes:
    """Download photo from Telegram."""
    file = await photo.get_file()
    return await file.download_as_bytearray()

def photo_to_text(photo) -> str:
    """Convert photo to text using OCR."""
    temp_image_path = None
    try:
        temp_dir = tempfile.gettempdir()
        temp_image_path = os.path.join(temp_dir, 'temp_image.png')
        image_bytes = io.BytesIO(photo)
        image = Image.open(image_bytes)
        image.save(temp_image_path)
        
        print('Using PaddleOCR')
        result = paddleocr.ocr(temp_image_path)
        
        if not result or not result[0]:
            return ''
        
        text_list = [line[1][0] for line in result[0]]
        full_text = ''.join(text_list)
        
        if is_chinese(full_text):
            cleaned_text = full_text
        else:
            print('English only detected, using pytesseract')
            full_text = pytesseract.image_to_string(image)
            cleaned_text = full_text
            
        return cleaned_text.strip() if cleaned_text.strip() else ''
        
    except Exception as e:
        print(f"Error in OCR processing: {str(e)}")
        return "Sorry, I couldn't process this image. Please try again with a clearer image."
    finally:
        if temp_image_path and os.path.exists(temp_image_path):
            os.remove(temp_image_path)

async def text_to_audio(text: str) -> tuple[bool, str]:
    """Convert text to audio using edge-tts."""
    try:
        temp_dir = tempfile.gettempdir()
        filename = create_safe_filename(text)
        temp_audio_path = os.path.join(temp_dir, filename)
        
        print(f'Using voice: {VOICE} for text: {text[:50]}...{text[-50:]}')
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(temp_audio_path)
        
        return True, temp_audio_path
    except Exception as e:
        print(f"Error in text-to-speech conversion: {str(e)}")
        return False, "Sorry, I couldn't convert this text to speech. Please try again."

# Telegram command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hello! I am ReadLooong, your personal reader. What would you like me to read?')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('I am ReadLooong, please send me any thing long to read. It could be a text, a picture, a link, etc.')

async def custom_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('This is a custom command!')

# Main message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main message handler for both text and photos."""
    message_type: str = update.message.chat.type
    text: str = update.message.text
    photo = update.message.photo[-1] if update.message.photo else None
    caption: str = update.message.caption
    chat_id = update.message.chat.id

    print(f'User ({chat_id}) says: "{text}" in {message_type}')
    
    # Initialize or update the last message time
    current_time = datetime.now()
    time_diff = (current_time - last_message_time[chat_id]).total_seconds()
    last_message_time[chat_id] = current_time

    async def process_accumulated_messages(chat_id):
        if not message_buffer[chat_id]:
            return
            
        # Check total length and combine buffered messages
        combined_text = "\n\n".join(message_buffer[chat_id])
        if len(combined_text) > MAX_BUFFER_SIZE:
            await update.message.reply_text("Message too long. Processing current buffer...")
        
        # Show the combined text that will be converted to audio
        await update.message.reply_text("Converting following text to audio:\n\n" + combined_text)
        
        start_time = datetime.now()
        
        # Convert to audio and send
        success, result = await text_to_audio(combined_text)
        
        # Check processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        if processing_time > MAX_PROCESSING_TIME:
            print(f"Warning: Processing took {processing_time} seconds")
            
        # Clear the buffer
        message_buffer[chat_id].clear()
        
        if success:
            try:
                await update.message.reply_audio(audio=open(result, 'rb'))
            finally:
                # Ensure file cleanup happens even if sending fails
                if os.path.exists(result):
                    os.remove(result)
        else:
            await update.message.reply_text(result)  # Send error message

    async def delayed_process(chat_id, current_batch_time: datetime):
        await asyncio.sleep(MESSAGE_TIMEOUT)
        # Only process if this is still the current batch
        if last_message_time[chat_id] == current_batch_time:
            await process_accumulated_messages(chat_id)

    # Process message based on type
    async def handle_content():
        if text:
            return text.replace(BOT_USERNAME, '').strip() if message_type == 'group' else text
        elif photo:
            if caption:
                print('Caption:', caption)
                return caption
            else:
                await update.message.reply_text('Converting to text...')
                photo_bytes = await download_photo(photo)
                return photo_to_text(photo_bytes)
        return None

    try:
        if message_type == 'group' and (not text or BOT_USERNAME not in text):
            return

        content = await handle_content()
        if content:
            if len(content) > MAX_BUFFER_SIZE:
                await update.message.reply_text("Message too long. Please send a shorter message.")
                return
            message_buffer[chat_id].append(content)

        # Process messages if timeout exceeded or message contains specific trigger
        if time_diff > MESSAGE_TIMEOUT or '!read' in str(content).lower():
            await process_accumulated_messages(chat_id)
        else:
            # If this is the first message in the buffer, schedule processing
            if len(message_buffer[chat_id]) == 1:
                asyncio.create_task(delayed_process(chat_id, current_time))

    except Exception as e:
        print(f"Error processing message: {str(e)}")
        await update.message.reply_text("Sorry, there was an error processing your message.")
        message_buffer[chat_id].clear()

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Update {update} caused error {context.error}')

# Main entry point
def main():
    print('Starting bot...')
    app = Application.builder().token(TOKEN).build()
    
    # Initialize handlers
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('custom', custom_command))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_message))
    app.add_error_handler(error)

    print('Polling...')
    app.run_polling(poll_interval=5)

if __name__ == '__main__':
    main()