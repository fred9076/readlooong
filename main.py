from typing import Final
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, JobQueue
from PIL import Image
import io
import os
import tempfile
import edge_tts
from paddleocr import PaddleOCR
import pytesseract
import numpy as np
import re
# import wordninja
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio

from dotenv import load_dotenv
load_dotenv()

TOKEN: Final = os.getenv('TELEGRAM_BOT_TOKEN')
BOT_USERNAME: Final = '@readlooong_bot'

# Use different voices for Chinese and English
VOICE_CN = "zh-CN-XiaoxiaoNeural"
VOICE_EN = "en-US-JennyNeural"

# At the top of the file, initialize PaddleOCR (do this only once)
ocr_chi_eng = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False, show_log=False, use_space_char=True)

# Commands
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hello! I am ReadLooong, your personal reader. What would you like me to read?')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('I am ReadLooong, please send me any thing long to read. It could be a text, a picture, a link, etc.')

async def custom_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('This is a custom command!')

# Responses


async def download_photo(photo) -> bytes:
    """Download the photo from Telegram and return as bytes"""
    file = await photo.get_file()
    return await file.download_as_bytearray()
    


def clean_eng_ocr_text(text: str) -> str:
    """
    Clean and normalize English OCR output text.
    Keeps multiple newlines but removes single newlines and special characters.
    """
    # Remove special character patterns
    text = re.sub(r'[!®°©]\s*', '', text)  # Remove special chars with optional spaces
    text = re.sub(r'\[\d+\]', '', text)     # Remove [number] citations
    text = re.sub(r'\d+!l\d+!', '', text)   # Remove patterns like '5!l2!'
    text = re.sub(r'\(\d+\[\d+\]', '', text)  # Remove patterns like (121[141
    text = re.sub(r'\d{1,2}:\d{1,2}(?::\d{1,2})?', '', text)  # Remove time patterns like 14:11:81 or 14:11
    
    # Replace single newlines with spaces
    text = re.sub(r'([^\n])\n([^\n])', r'\1 \2', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    # Replace multiple spaces with single space 
    text = re.sub(r'\s+', ' ', text)
    
    return text

def is_chinese(text: str) -> bool:
    """Check if the text contains Chinese characters more than 50%."""
    chinese_chars = sum('\u4e00' <= char <= '\u9fff' for char in text)
    return chinese_chars > len(text) * 0.9



def photo_to_text(photo) -> str:
    try:
        # Create temporary file and save image
        temp_dir = tempfile.gettempdir()
        temp_image_path = os.path.join(temp_dir, 'temp_image.png')
        image_bytes = io.BytesIO(photo)
        image = Image.open(image_bytes)
        image.save(temp_image_path)
        
        # Try PaddleOCR first
        print('Using PaddleOCR')
        result = ocr_chi_eng.ocr(temp_image_path)
        
        if not result or not result[0]:
            return ''          
        
        # Extract text from PaddleOCR result
        text_list = [line[1][0] for line in result[0]]
        full_text = ''.join(text_list)
        
        # Check if result contains Chinese
        if is_chinese(full_text):
            # Extract text from PaddleOCR result            
            os.remove(temp_image_path)
            # cleaned_text = clean_chi_ocr_text(full_text)
            cleaned_text = full_text
        else:
            print('English only detected, using pytesseract')
            full_text = pytesseract.image_to_string(image)
            os.remove(temp_image_path)
            # cleaned_text = clean_eng_ocr_text(full_text)
            cleaned_text = full_text
        return cleaned_text.strip() if cleaned_text.strip() else ''
        
    except Exception as e:
        print(f"Error in OCR processing: {str(e)}")
        return "Sorry, I couldn't process this image. Please try again with a clearer image."

def create_safe_filename(text: str, max_length: int = 50) -> str:
    """Create a safe filename from text content."""
    # Take first few characters of the text
    safe_text = text[:max_length]
    # Remove or replace unsafe filename characters
    safe_text = re.sub(r'[^a-zA-Z0-9\s-]', '', safe_text)
    # Replace spaces with underscores and convert to lowercase
    safe_text = safe_text.strip().replace(' ', '_').lower()
    # Add timestamp to ensure uniqueness
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{safe_text}_{timestamp}.mp3"

async def text_to_audio(text: str) -> tuple[bool, str]:
    try:
        temp_dir = tempfile.gettempdir()
        
        # Generate filename based on text content
        filename = create_safe_filename(text)
        print(f"Generated filename: {filename}")
        temp_audio_path = os.path.join(temp_dir, filename)

        # Select voice based on text content
        voice = VOICE_CN if is_chinese(text) else VOICE_EN
        print(f'Using voice: {voice} for text: {text[:50]}...')
        
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(temp_audio_path)

        return True, temp_audio_path
        
    except Exception as e:
        print(f"Error in text-to-speech conversion: {str(e)}")
        return False, "Sorry, I couldn't convert this text to speech. Please try again."

MESSAGE_TIMEOUT = 10  # seconds to wait for additional messages
MAX_BUFFER_SIZE = 1000000  # maximum characters in buffer
MAX_PROCESSING_TIME = 30  # maximum seconds to process audio

message_buffer = defaultdict(list)
last_message_time = defaultdict(datetime.now)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            await update.message.reply_audio(audio=open(result, 'rb'))
            os.remove(result)
        else:
            await update.message.reply_text(result)  # Send error message

    async def delayed_process(chat_id):
        await asyncio.sleep(MESSAGE_TIMEOUT)
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
            message_buffer[chat_id].append(content)

        # Process messages if timeout exceeded or message contains specific trigger
        if time_diff > MESSAGE_TIMEOUT or '!read' in str(content).lower():
            await process_accumulated_messages(chat_id)
        else:
            # If this is the first message in the buffer, schedule processing
            if len(message_buffer[chat_id]) == 1:
                asyncio.create_task(delayed_process(chat_id))

    except Exception as e:
        print(f"Error processing message: {str(e)}")
        await update.message.reply_text("Sorry, there was an error processing your message.")
        message_buffer[chat_id].clear()

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Update {update} caused error {context.error}')

def clean_chi_ocr_text(text: str) -> str:
    """Clean and normalize Chinese OCR output text."""
    if not text:
        return ""
    
    # Normalize Unicode characters
    text = unicodedata.normalize('NFKC', text)
    
    # Remove time patterns
    text = re.sub(r'\d{1,2}:\d{1,2}(?::\d{1,2})?', '', text)  # Remove time patterns like 14:11:81 or 14:11
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', '', text)
    
    return text.strip()

if __name__ == '__main__':
    print('Starting bot...')
    app = Application.builder().token(TOKEN).build()
    
    # Initialize the job queue
    job_queue = app.job_queue

    # Commands
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('custom', custom_command))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_message))

    # Errors
    app.add_error_handler(error)

    print('Polling...')
    app.run_polling(poll_interval=5)