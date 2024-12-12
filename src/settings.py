from typing import Final
import os
from dotenv import load_dotenv
from .config.lang_voice import LANG_VOICE_CONFIGS

# Load environment variables
load_dotenv()

# Bot Configuration
TOKEN: Final = os.getenv('TELEGRAM_BOT_TOKEN')
BOT_USERNAME: Final = '@readlooong_bot'

# Get language config
selected_language = os.getenv('LANGUAGE', 'zh')
language_config = LANG_VOICE_CONFIGS.get(selected_language, LANG_VOICE_CONFIGS['zh'])

LANGUAGE = language_config['language']
VOICE = language_config['voice']
OCR_LANG = language_config['ocr_lang']

# Message Processing
MESSAGE_TIMEOUT = 10  # seconds to wait for additional messages
MAX_BUFFER_SIZE = 1000000  # maximum characters in buffer
MAX_PROCESSING_TIME = 30  # maximum seconds to process audio