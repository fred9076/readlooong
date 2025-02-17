# 📚 ReadLooong Telegram Bot

ReadLooong is a Telegram bot that converts various content types to speech. It supports text, images, and videos from multiple platforms, making it perfect for language learning, accessibility, and content consumption on the go.

## ✨ Features

- 🗣️ Text-to-Speech conversion for multiple languages
  - 🇨🇳 Chinese (Mandarin)
  - 🇺🇸 English
  - 🌐 More languages can be added via configuration
- 👀 Advanced OCR (Optical Character Recognition)
  - PaddleOCR for Chinese text
  - EasyOCR for other languages
  - Automatic language detection
  - GPU acceleration support
- 🎥 Video audio extraction from multiple platforms:
  - YouTube
  - Bilibili
- 🔗 Link text extraction and reading
- 👥 Supports both private chats and group conversations
- 📦 Message buffering for processing multiple messages together

## 🚀 Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/readlooong-bot.git
cd readlooong-bot
```
2. Install ffmpeg for video processing
   - macos:   brew install ffmpeg
   - ubuntu:  sudo apt update
              sudo apt install ffmpeg
   
3. Create a virtual env and Install dependencies:
```bash
pip install -r requirements.txt
```
4. create a new telegram bot and get bot token
    - [Creating a new bot](https://core.telegram.org/bots/features#creating-a-new-bot/)

5. Set up environment variables in `.env`:   
```env
TELEGRAM_BOT_TOKEN=your_bot_token  
BOT_NAME=@your_bot_name
LANGUAGE=zh  # or 'en' for English
USE_GPU=false  # Set to 'true' to enable GPU acceleration
```

## 📖 Usage

1. Start the bot: `/start`
2. Send any of the following:
   - 📝 Text messages
   - 🖼️ Images with text (OCR supported)
   - 🔗 URLs to articles or YouTube videos
   - 📄 PDF or EPUB files

The bot will process the content and send back an 🎵 audio file.

## ⚙️ Configuration

- 🌍 Language settings can be configured in `src/config/lang_voice.py`
- 📸 OCR settings:
  - Chinese text uses PaddleOCR
  - Other languages use EasyOCR
  - GPU acceleration can be enabled via USE_GPU environment variable

## 🛠️ Built With

- [python-telegram-bot](https://python-telegram-bot.org/) - Telegram Bot API wrapper
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - OCR engine for Chinese
- [EasyOCR](https://github.com/JaidedAI/EasyOCR) - OCR engine for other languages
- [edge-tts](https://github.com/rany2/edge-tts) - Text to Speech
- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF processing
- [Flask](https://flask.palletsprojects.com/) - Web framework for deployment

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Thanks to Microsoft Edge TTS for providing the text-to-speech service
- Thanks to PaddleOCR team for the excellent OCR engine
- Thanks to EasyOCR team for the multilingual OCR support
- Thanks to all the open-source libraries that made this project possible

## 💬 Support

For support, please open an issue in the GitHub repository.

