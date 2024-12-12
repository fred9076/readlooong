from datetime import datetime
from collections import defaultdict
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os

from .settings import (
    TOKEN, BOT_USERNAME, MESSAGE_TIMEOUT, 
    MAX_BUFFER_SIZE, MAX_PROCESSING_TIME
)
from .ocr import OCRProcessor
from .text_to_speech import convert_to_audio

class TelegramBot:
    def __init__(self):
        self.message_buffer = defaultdict(list)
        self.last_message_time = defaultdict(datetime.now)
        self.ocr_processor = OCRProcessor()

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            'Hello! I am ReadLooong, your personal reader. What would you like me to read?'
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            'I am ReadLooong, please send me any thing long to read. '
            'It could be a text, a picture, a link, etc.'
        )

    async def download_photo(self, photo) -> bytes:
        """Download photo from Telegram."""
        file = await photo.get_file()
        return await file.download_as_bytearray()

    async def process_accumulated_messages(self, update: Update, chat_id: int):
        if not self.message_buffer[chat_id]:
            return
            
        combined_text = "\n\n".join(self.message_buffer[chat_id])
        if len(combined_text) > MAX_BUFFER_SIZE:
            await update.message.reply_text("Message too long. Processing current buffer...")
        
        await update.message.reply_text("Converting following text to audio:\n\n" + combined_text)
        
        start_time = datetime.now()
        success, result = await convert_to_audio(combined_text)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        if processing_time > MAX_PROCESSING_TIME:
            print(f"Warning: Processing took {processing_time} seconds")
            
        self.message_buffer[chat_id].clear()
        
        if success:
            try:
                await update.message.reply_audio(audio=open(result, 'rb'))
            finally:
                if os.path.exists(result):
                    os.remove(result)
        else:
            await update.message.reply_text(result)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main message handler for both text and photos."""
        message_type: str = update.message.chat.type
        text: str = update.message.text
        photo = update.message.photo[-1] if update.message.photo else None
        caption: str = update.message.caption
        chat_id = update.message.chat.id

        print(f'User ({chat_id}) says: "{text}" in {message_type}')
        
        current_time = datetime.now()
        time_diff = (current_time - self.last_message_time[chat_id]).total_seconds()
        self.last_message_time[chat_id] = current_time

        try:
            if message_type == 'group' and (not text or BOT_USERNAME not in text):
                return

            content = await self._handle_content(update)
            if content:
                if len(content) > MAX_BUFFER_SIZE:
                    await update.message.reply_text("Message too long. Please send a shorter message.")
                    return
                self.message_buffer[chat_id].append(content)

            if time_diff > MESSAGE_TIMEOUT or '!read' in str(content).lower():
                await self.process_accumulated_messages(update, chat_id)
            elif len(self.message_buffer[chat_id]) == 1:
                asyncio.create_task(self._delayed_process(update, chat_id, current_time))

        except Exception as e:
            print(f"Error processing message: {str(e)}")
            await update.message.reply_text("Sorry, there was an error processing your message.")
            self.message_buffer[chat_id].clear()

    async def _handle_content(self, update: Update) -> str:
        """Process message content based on type."""
        text = update.message.text
        photo = update.message.photo[-1] if update.message.photo else None
        caption = update.message.caption
        message_type = update.message.chat.type

        if text:
            return text.replace(BOT_USERNAME, '').strip() if message_type == 'group' else text
        elif photo:
            if caption:
                print('Caption:', caption)
                return caption
            else:
                await update.message.reply_text('Converting to text...')
                photo_bytes = await self.download_photo(photo)
                return self.ocr_processor.process_image(photo_bytes)
        return None

    async def _delayed_process(self, update: Update, chat_id: int, current_batch_time: datetime):
        await asyncio.sleep(MESSAGE_TIMEOUT)
        if self.last_message_time[chat_id] == current_batch_time:
            await self.process_accumulated_messages(update, chat_id)

    async def error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        print(f'Update {update} caused error {context.error}')

    def run(self):
        """Start the bot."""
        print('Starting bot...')
        app = Application.builder().token(TOKEN).build()
        
        # Initialize handlers
        app.add_handler(CommandHandler('start', self.start_command))
        app.add_handler(CommandHandler('help', self.help_command))
        app.add_handler(MessageHandler(filters.TEXT, self.handle_message))
        app.add_handler(MessageHandler(filters.PHOTO, self.handle_message))
        app.add_error_handler(self.error)

        print('Polling...')
        app.run_polling(poll_interval=5) 