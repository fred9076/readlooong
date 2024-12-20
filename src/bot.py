from datetime import datetime
from collections import defaultdict
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os
import re
import tempfile

from .config import (
    TOKEN, BOT_USERNAME, MESSAGE_TIMEOUT, 
    MAX_BUFFER_SIZE, MAX_PROCESSING_TIME
)
from .ocr import OCRProcessor
from .text_to_speech import convert_to_audio
from .link import LinkProcessor

class TelegramBot:
    def __init__(self):
        print('Initializing bot...')
        # Clear any existing buffers
        self.message_buffer = defaultdict(list)
        self.last_message_time = defaultdict(datetime.now)
        self.ocr_processor = OCRProcessor()
        self.processing_locks = defaultdict(asyncio.Lock)  # Add lock per chat
        self.link_processor = LinkProcessor()
        self.debug_mode = False  # Add debug mode flag
        self._cleanup_buffers()

    def _cleanup_buffers(self):
        """Clean up all message buffers and timestamps."""
        self.message_buffer.clear()
        self.last_message_time.clear()
        print('Message buffers cleared')

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
        """Process accumulated messages with improved link handling."""
        if not self.message_buffer[chat_id]:
            return
        
        async with self.processing_locks[chat_id]:
            try:
                messages_to_process = self.message_buffer[chat_id].copy()
                self.message_buffer[chat_id].clear()
                
                # Process messages based on type
                for message in messages_to_process:
                    # Skip empty messages
                    if not message or not message.strip():
                        continue
                    
                    # Determine message type and extract content
                    if message.startswith('Link: '):
                        text = message[6:]  # Remove 'Link: ' prefix
                        prefix = "🔗 Link content"
                    elif message.startswith('OCR: '):
                        text = message[5:]  # Remove 'OCR: ' prefix
                        prefix = "📸 Image text"
                    elif message.startswith('Caption: '):
                        text = message[8:]  # Remove 'Caption: ' prefix
                        prefix = "📝 Image caption"
                    else:
                        text = message
                        prefix = "📝 Text"

                    if len(text) > MAX_BUFFER_SIZE:
                        await update.message.reply_text(f"⚠️ Skipping - content too long ({len(text)} characters)")
                        continue

                    try:
                        # First, send debug file if in debug mode
                        if self.debug_mode:
                            debug_msg = await update.message.reply_text("📝 Preparing debug file...")
                            try:
                                # Create and send debug file
                                with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False, encoding='utf-8') as tmp:
                                    tmp.write(f"{prefix}:\n\n{text}\n\nLength: {len(text)} characters")
                                    tmp_path = tmp.name

                                await update.message.reply_document(
                                    document=open(tmp_path, 'rb'),
                                    filename=f"debug_content_{len(text)}_chars.txt",
                                    caption=f"{prefix} - {len(text)} characters"
                                )
                            finally:
                                # Clean up
                                if 'tmp_path' in locals() and os.path.exists(tmp_path):
                                    os.remove(tmp_path)
                                await debug_msg.delete()

                        # Then show preview
                        preview = text[:1000] + "..." if len(text) > 1000 else text
                        await update.message.reply_text(
                            f"{prefix}:\n\n"
                            f"{preview}\n\n"
                            f"Length: {len(text)} characters"
                        )

                        # Finally convert to audio
                        converting_msg = await update.message.reply_text("🎯 Converting to audio...")
                        try:
                            success, result = await asyncio.wait_for(
                                convert_to_audio(text),
                                timeout=MAX_PROCESSING_TIME
                            )
                            
                            if success:
                                try:
                                    await update.message.reply_audio(
                                        audio=open(result, 'rb'),
                                        caption=f"{prefix} converted to audio"
                                    )
                                finally:
                                    if os.path.exists(result):
                                        os.remove(result)
                                    await converting_msg.delete()
                            else:
                                await update.message.reply_text(f"❌ Error converting: {result}")
                                await converting_msg.delete()
                        
                        except asyncio.TimeoutError:
                            await update.message.reply_text("⏱️ Processing took too long, skipping...")
                            await converting_msg.delete()
                        except Exception as e:
                            print(f"Error processing message: {str(e)}")
                            await update.message.reply_text("❌ Error processing this content")
                            await converting_msg.delete()

                    except Exception as e:
                        print(f"Error processing message: {str(e)}")
                        await update.message.reply_text("❌ Error processing this content")

            except Exception as e:
                print(f"Error in process_accumulated_messages: {str(e)}")
                await update.message.reply_text("❌ Sorry, there was an error processing your messages.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main message handler for both text and photos."""
        message_type: str = update.message.chat.type
        text: str = update.message.text
        photo = update.message.photo[-1] if update.message.photo else None
        caption: str = update.message.caption
        chat_id = update.message.chat.id

        # Debug logging
        print(f'User ({chat_id}) in {message_type}:', end=' ')
        if text:
            print(f'text: "{text}"')
        elif photo:
            print(f'photo with caption: "{caption}"' if caption else 'photo without caption')

        current_time = datetime.now()
        time_diff = (current_time - self.last_message_time[chat_id]).total_seconds()
        self.last_message_time[chat_id] = current_time

        try:
            # Skip if group message without mention
            if message_type == 'group' and (not text or BOT_USERNAME not in text):
                return

            # Check if buffer is getting too large
            if len(self.message_buffer[chat_id]) >= 10:  # Limit to 10 messages
                await update.message.reply_text("Too many pending messages. Processing current buffer...")
                await self.process_accumulated_messages(update, chat_id)
                return

            content = await self._handle_content(update)
            if content:
                if len(content) > MAX_BUFFER_SIZE:
                    await update.message.reply_text("Message too long. Please send a shorter message.")
                    return
            
                print(f'Adding to buffer: "{content[:50]}..."')
                self.message_buffer[chat_id].append(content)

                # Always schedule/reschedule delayed processing
                if time_diff > MESSAGE_TIMEOUT or '!read' in str(content).lower():
                    # Process immediately if timeout exceeded or forced
                    await self.process_accumulated_messages(update, chat_id)
                else:
                    # Cancel any existing delayed task
                    if hasattr(self, f'delayed_task_{chat_id}'):
                        task = getattr(self, f'delayed_task_{chat_id}')
                        if not task.done():
                            task.cancel()
                    
                    # Schedule new delayed processing
                    task = asyncio.create_task(self._delayed_process(update, chat_id, current_time))
                    setattr(self, f'delayed_task_{chat_id}', task)

        except Exception as e:
            print(f"Error processing message: {str(e)}")
            await update.message.reply_text("Sorry, there was an error processing your message.")
            self.message_buffer[chat_id].clear()

    async def _handle_content(self, update: Update) -> str:
        """Process message content based on type."""
        text = update.message.text
        photo = update.message.photo[-1] if update.message.photo else None
        caption = update.message.caption
        entities = update.message.entities
        message_type = update.message.chat.type
        chat_id = update.message.chat.id

        # Handle URLs first
        if text:
            # Extract URLs from text
            urls = []
            if entities:
                for entity in entities:
                    if entity.type == "url":
                        url = text[entity.offset:entity.offset + entity.length]
                        urls.append(url)
            
            # Also try to find URLs in plain text
            if not urls:
                url_pattern = r'https?://\S+'
                import re
                urls = re.findall(url_pattern, text)

            if urls:
                combined_text = []
                for url in urls:
                    await update.message.reply_text(f'📄 Extracting text from: {url}')
                    link_text = await self.link_processor.process_link(url)
                    if link_text:
                        # Don't clean link text, just append it directly
                        combined_text.append(link_text)
                    else:
                        await update.message.reply_text("❌ Couldn't extract text from this link.")
                
                if combined_text:
                    # Return link text without additional cleaning
                    return "Link: " + "\n\n".join(combined_text)
                return None

            # For regular text, apply cleaning
            cleaned_text = self._clean_text(text.replace(BOT_USERNAME, '').strip()) if message_type == 'group' else self._clean_text(text)
            return cleaned_text

        elif photo:
            if caption:
                # Clean caption text
                cleaned_caption = self._clean_text(caption)
                print('Using cleaned caption:', cleaned_caption)
                return f'Caption: {cleaned_caption}'
            else:
                # Check if there are any text or caption messages in the buffer
                has_text_in_buffer = any(
                    not msg.startswith('OCR: ') 
                    for msg in self.message_buffer[chat_id]
                )
                
                if has_text_in_buffer:
                    print('Skipping OCR due to text/caption in buffer')
                    return None
                else:
                    await update.message.reply_text('Converting image to text...')
                    photo_bytes = await self.download_photo(photo)
                    ocr_text = self.ocr_processor.process_image(photo_bytes)
                    # Clean OCR text
                    cleaned_ocr = self._clean_text(ocr_text) if ocr_text else None
                    return f'OCR: {cleaned_ocr}' if cleaned_ocr else None
        return None

    def _clean_text(self, text: str) -> str:
        """Clean and format text messages."""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        return '\n\n'.join(paragraphs)

    async def _delayed_process(self, update: Update, chat_id: int, current_batch_time: datetime):
        await asyncio.sleep(MESSAGE_TIMEOUT)
        if self.last_message_time[chat_id] == current_batch_time:
            await self.process_accumulated_messages(update, chat_id)

    async def error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        print(f'Update {update} caused error {context.error}')
        await self.link_processor.close()

    async def toggle_debug(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Toggle debug mode on/off."""
        self.debug_mode = not self.debug_mode
        status = "enabled" if self.debug_mode else "disabled"
        await update.message.reply_text(f"Debug mode {status} 🛠")

    def run(self):
        """Start the bot."""
        print('Starting bot...')
        app = Application.builder().token(TOKEN).build()
        
        # Initialize handlers
        app.add_handler(CommandHandler('start', self.start_command))
        app.add_handler(CommandHandler('help', self.help_command))
        app.add_handler(CommandHandler('debug', self.toggle_debug))  # Add debug command
        app.add_handler(MessageHandler(filters.TEXT, self.handle_message))
        app.add_handler(MessageHandler(filters.PHOTO, self.handle_message))
        app.add_error_handler(self.error)

        print('Polling...')
        app.run_polling(poll_interval=5) 