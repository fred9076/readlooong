from typing import Final
import os
import logging
from dotenv import load_dotenv
from .lang_voice import LANG_VOICE_CONFIGS

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Bot Configuration
TOKEN: Final = os.getenv('TELEGRAM_BOT_TOKEN')
BOT_USERNAME: Final = os.getenv('BOT_NAME')

# Hardware Configuration
USE_GPU: Final = os.getenv('USE_GPU', 'false').lower() == 'true'

# Get language config with validation
selected_language = os.getenv('LANGUAGE', 'zh')
if selected_language not in LANG_VOICE_CONFIGS:
    logger.warning(f"Unsupported language {selected_language}, falling back to 'zh'")
    selected_language = 'zh'

language_config = LANG_VOICE_CONFIGS[selected_language]

LANGUAGE = language_config['language']
VOICE = language_config['voice']
OCR_LANG = language_config['ocr_lang']

# OCR settings
USE_EASY_OCR = selected_language != 'zh'  # Use easyOCR for non-Chinese languages

# Message Processing
MESSAGE_TIMEOUT = 1  # seconds to wait for additional messages
MAX_BUFFER_SIZE = 400000  # maximum characters in buffer
MAX_PROCESSING_TIME = 60  # maximum seconds to process audio 