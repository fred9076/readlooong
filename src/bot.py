from datetime import datetime
from collections import defaultdict
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os
import re
import tempfile
import time
import logging

from .config import (
    TOKEN, BOT_USERNAME, MESSAGE_TIMEOUT, 
    MAX_BUFFER_SIZE, MAX_PROCESSING_TIME,
)
from .ocr import OCRProcessor
from .text_to_speech import convert_to_audio
from .link import LinkProcessor
from .ebook import EbookProcessor

WORDS_PER_MINUTE = 300
CHARS_PER_WORD = 3
PROCESSING_OVERHEAD = 1.1
PROGRESS_CHECK_INTERVAL = 10
STUCK_CHECK_TIMEOUT = 30

class ConversionProgress:
    def __init__(self, total_chars):
        self.total_chars = total_chars
        self.processed_chars = 0
        self.last_update = time.time()

    def update(self, processed_chars):
        self.processed_chars = processed_chars
        self.last_update = time.time()

    @property
    def progress_ratio(self):
        return self.processed_chars / self.total_chars if self.total_chars > 0 else 0

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
        self.ebook_processor = EbookProcessor()
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
            'I can handle:\n'
            '- Text messages\n'
            '- Images (with OCR)\n'
            '- Links (web pages and videos)\n'
            '- Ebooks (PDF, EPUB)\n'
            'I will convert the content to audio for you to listen to.'
        )

    async def download_photo(self, photo) -> bytes:
        """Download photo from Telegram."""
        file = await photo.get_file()
        return await file.download_as_bytearray()

    async def process_accumulated_messages(self, update: Update, chat_id: int):
        """Process accumulated messages with improved error handling."""
        if not self.message_buffer[chat_id]:
            return
        
        async with self.processing_locks[chat_id]:
            try:
                messages_to_process = self.message_buffer[chat_id].copy()
                self.message_buffer[chat_id].clear()
                
                for message in messages_to_process:
                    if not message or not message.strip():
                        continue
                    
                    try:
                        # Extract content and prefix
                        if message.startswith('Link: '):
                            text = message[6:]
                            prefix = "🔗 Link content"
                        elif message.startswith('OCR: '):
                            text = message[5:]
                            prefix = "📸 Image text"
                        elif message.startswith('Caption: '):
                            text = message[8:]
                            prefix = "📝 Image caption"
                        else:
                            text = message
                            prefix = "📝 Text"

                        if len(text) > MAX_BUFFER_SIZE:
                            await update.message.reply_text(f"⚠️ Content too long ({len(text)} characters)")
                            continue

                        # Show preview
                        preview = text[:1000] + "..." if len(text) > 1000 else text
                        await update.message.reply_text(
                            f"{prefix}:\n\n{preview}\n\nLength: {len(text)} characters"
                        )

                        # Convert to audio with progress tracking
                        converting_msg = await update.message.reply_text(
                            "🎯 Starting audio conversion...\n"
                            f"Content length: {len(text)} characters"
                        )

                        try:
                            # Create progress tracker
                            progress = ConversionProgress(len(text))
                            conversion_task = asyncio.create_task(convert_to_audio(text, progress))
                            start_time = time.time()
                            last_progress_time = start_time

                            while not conversion_task.done():
                                try:
                                    current_time = time.time()
                                    elapsed = current_time - start_time

                                    # Update progress message periodically
                                    if current_time - last_progress_time >= PROGRESS_CHECK_INTERVAL:
                                        elapsed_seconds = int(elapsed)
                                        progress_ratio = progress.progress_ratio
                                        
                                        if progress_ratio > 0:
                                            # Calculate remaining time based on actual progress
                                            remaining_seconds = int(elapsed_seconds * (1 - progress_ratio) / progress_ratio)
                                        else:
                                            # Initial estimate
                                            is_chinese = any('\u4e00' <= char <= '\u9fff' for char in text[:100])
                                            chars_per_second = 50 if is_chinese else 30
                                            remaining_seconds = int(len(text) / chars_per_second)

                                        await converting_msg.edit_text(
                                            f"🎯 Converting to audio...\n"
                                            f"Progress: {progress_ratio:.1%}\n"
                                            f"Time elapsed: {self._format_time(elapsed_seconds)}\n"
                                            f"Estimated remaining: {self._format_time(remaining_seconds)}"
                                        )
                                        last_progress_time = current_time

                                    await asyncio.sleep(1)

                                except asyncio.CancelledError:
                                    await update.message.reply_text("❌ Conversion was cancelled")
                                    break
                                except Exception as e:
                                    print(f"Error during conversion: {str(e)}")
                                    await update.message.reply_text(f"❌ Conversion error: {str(e)}")
                                    break

                            if not conversion_task.cancelled():
                                success, result = await conversion_task
                                if success:
                                    try:
                                        await update.message.reply_audio(
                                            audio=open(result, 'rb'),
                                            caption=f"{prefix} converted to audio"
                                        )
                                    finally:
                                        if os.path.exists(result):
                                            os.remove(result)
                                else:
                                    await update.message.reply_text(f"❌ Conversion failed: {result}")

                        except Exception as e:
                            print(f"Error in audio conversion: {str(e)}")
                            await update.message.reply_text("❌ Error during audio conversion")
                        finally:
                            try:
                                await converting_msg.delete()
                            except:
                                pass

                    except Exception as e:
                        print(f"Error processing message: {str(e)}")
                        await update.message.reply_text("❌ Error processing this content")

            except Exception as e:
                print(f"Error in message processing: {str(e)}")
                await update.message.reply_text("❌ An error occurred while processing messages")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main message handler for both text and photos."""
        try:
            message_type: str = update.message.chat.type
            text: str = update.message.text
            photo = update.message.photo[-1] if update.message.photo else None
            caption: str = update.message.caption
            document = update.message.document
            chat_id = update.message.chat_id

            # Debug logging
            print(f'User ({chat_id}) in {message_type}:', end=' ')
            if text:
                print(f'text: "{text}"')
            elif photo:
                print(f'photo with caption: "{caption}"' if caption else 'photo without caption')
            elif document:
                print(f'document: "{document.file_name}" ({document.mime_type})')

            # Handle documents first
            if document:
                mime_type = document.mime_type
                if mime_type in ['application/pdf', 'application/epub+zip', 'application/x-mobipocket-ebook']:
                    await self._handle_ebook(update, document)
                    return

            # Rest of the existing handle_message code...
            current_time = datetime.now()
            time_diff = (current_time - self.last_message_time[chat_id]).total_seconds()
            self.last_message_time[chat_id] = current_time

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
            
            if not urls:
                url_pattern = r'https?://\S+'
                urls = re.findall(url_pattern, text)

            if urls:
                for url in urls:
                    # Check if it's a video URL
                    if self.link_processor.video_processor.is_supported_url(url):
                        status_msg = await update.message.reply_text(f'🎥 Processing video: {url}')
                        try:
                            success, result = await self.link_processor.video_processor.extract_audio(url)
                            if success:
                                try:
                                    await status_msg.edit_text("⏳ Sending audio file...")
                                    await update.message.reply_audio(
                                        audio=open(result, 'rb'),
                                        caption=f"Audio extracted from video",
                                        filename=f"audio_{os.path.basename(result)}"
                                    )
                                except Exception as e:
                                    await update.message.reply_text(
                                        f"❌ Error sending audio: {str(e)}\n"
                                        f"This might be because the file is too large or in an unsupported format."
                                    )
                                finally:
                                    # Clean up the temporary files
                                    if os.path.exists(result):
                                        try:
                                            os.remove(result)
                                            os.rmdir(os.path.dirname(result))
                                        except Exception as cleanup_error:
                                            print(f"Cleanup error: {cleanup_error}")
                            else:
                                await update.message.reply_text(
                                    f"❌ Failed to extract audio:\n{result}\n\n"
                                    f"Please make sure the video is accessible and not private/restricted."
                                )
                        except Exception as e:
                            await update.message.reply_text(
                                f"❌ Unexpected error while processing video:\n{str(e)}"
                            )
                        finally:
                            await status_msg.delete()
                        return None

                    # Process as regular link
                    await update.message.reply_text(f'📄 Extracting text from: {url}')
                    link_text = await self.link_processor.process_link(url)
                    if link_text:
                        return "Link: " + link_text
                    else:
                        await update.message.reply_text("❌ Couldn't extract text from this link.")
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

    async def _handle_ebook(self, update: Update, document):
        """Handle ebook document processing."""
        try:
            processing_msg = await update.message.reply_text("📚 Processing ebook...")
            
            # Download the file
            file = await document.get_file()
            file_bytes = await file.download_as_bytearray()
            
            # Process the ebook
            success, result = await self.ebook_processor.process_ebook(file_bytes)
            
            if success:
                if isinstance(result, list):  # EPUB chapters or PDF sections
                    total_parts = len(result)
                    await update.message.reply_text(
                        f"📖 Found {total_parts} parts. Processing each part..."
                    )
                    
                    for part_num, (part_title, part_content) in enumerate(result, 1):
                        # Clean the content
                        cleaned_content = self._clean_text(part_content)
                        
                        if len(cleaned_content) > MAX_BUFFER_SIZE:
                            await update.message.reply_text(
                                f"⚠️ Part {part_num}/{total_parts}: {part_title} is too long "
                                f"({len(cleaned_content)} characters), splitting..."
                            )
                            # Split into smaller chunks
                            chunks = self._split_content(cleaned_content)
                            for chunk_num, chunk in enumerate(chunks, 1):
                                if len(chunk) > MAX_BUFFER_SIZE:
                                    await update.message.reply_text(
                                        f"⚠️ Chunk {chunk_num} is too long, skipping..."
                                    )
                                    continue
                                
                                # Process chunk
                                chat_id = update.message.chat_id
                                self.message_buffer[chat_id].append(
                                    f"{part_title} (Part {chunk_num})\n\n{chunk}"
                                )
                                await self.process_accumulated_messages(update, chat_id)
                                self.message_buffer[chat_id].clear()
                        else:
                            # Process normal-sized part
                            chat_id = update.message.chat_id
                            self.message_buffer[chat_id].append(
                                f"{part_title}\n\n{cleaned_content}"
                            )
                            await self.process_accumulated_messages(update, chat_id)
                            self.message_buffer[chat_id].clear()
                        
                        # Show progress
                        if part_num % 5 == 0 or part_num == total_parts:
                            await update.message.reply_text(
                                f"📚 Progress: {part_num}/{total_parts} parts processed"
                            )
                    
                    await update.message.reply_text("✅ Finished processing all parts!")
                else:
                    await update.message.reply_text(
                        "❌ Unexpected result format. Please try again."
                    )
            else:
                await update.message.reply_text(f"❌ {result}")
            
            await processing_msg.delete()
            
        except Exception as e:
            print(f"Error processing ebook: {str(e)}")
            await update.message.reply_text("❌ Sorry, there was an error processing your ebook.")

    def _split_content(self, content: str, max_size: int = MAX_BUFFER_SIZE) -> list:
        """Split content into smaller chunks at sentence boundaries."""
        chunks = []
        current_chunk = []
        current_size = 0
        
        # Split into sentences (basic implementation)
        sentences = re.split(r'(?<=[.!?])\s+', content)
        
        for sentence in sentences:
            sentence_size = len(sentence)
            if current_size + sentence_size > max_size:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_size = sentence_size
            else:
                current_chunk.append(sentence)
                current_size += sentence_size
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks

    def _format_time(self, seconds: int) -> str:
        """Format seconds into a readable time string."""
        if seconds < 60:
            return f"{seconds} seconds"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes} minutes {secs} seconds"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours} hours {minutes} minutes"

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理照片消息"""
        try:
            chat_id = update.effective_chat.id
            photo_file = await update.message.photo[-1].get_file()
            photo_bytes = await photo_file.download_as_bytearray()
            
            # 直接调用process_image，不需要await
            text = self.ocr_processor.process_image(photo_bytes)
            
            if not text:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="Sorry, I couldn't extract any text from this image."
                )
                return
                
            await context.bot.send_message(
                chat_id=chat_id,
                text=text
            )
            
        except Exception as e:
            logger.error(f"Error processing photo: {str(e)}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="Sorry, there was an error processing your photo. Please try again."
            )

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理文档消息"""
        try:
            # ... 其他代码保持不变 ...
            
            # 处理PDF页面
            for page_num, image in enumerate(images, 1):
                # 直接调用process_pdf_page，不需要await
                text = self.ocr_processor.process_pdf_page(image)
                if text:
                    self.message_buffer[chat_id].append(text)
                    
            # ... 其他代码保持不变 ...
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="Sorry, there was an error processing your document. Please try again."
            )

    def run(self):
        """Start the bot."""
        print('Starting bot...')
        app = Application.builder().token(TOKEN).build()
        
        # Initialize handlers
        app.add_handler(CommandHandler('start', self.start_command))
        app.add_handler(CommandHandler('help', self.help_command))
        app.add_handler(CommandHandler('debug', self.toggle_debug))
        app.add_handler(MessageHandler(filters.TEXT, self.handle_message))
        app.add_handler(MessageHandler(filters.PHOTO, self.handle_message))
        app.add_handler(MessageHandler(filters.Document.ALL, self.handle_message))
        app.add_error_handler(self.error)

        print('Polling...')
        app.run_polling(poll_interval=5) 