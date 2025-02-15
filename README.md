# ReadLooong Telegram Bot

ReadLooong is a Telegram bot that converts various content types to speech. It supports text, images, and videos from multiple platforms, making it perfect for language learning, accessibility, and content consumption on the go.

## Features

- Text-to-Speech conversion for both English and Chinese
- OCR (Optical Character Recognition) support for images
- Video audio extraction from multiple platforms:
  - YouTube
  - Bilibili
- Link text extraction and reading
- Supports both private chats and group conversations
- Message buffering for processing multiple messages together
- Automatic language detection and voice selection

## Installation

1. Clone the repository:
```

## Usage

1. Start the bot: `/start`
2. Send any of the following:
   - Text messages
   - Images with text
   - URLs to articles or YouTube videos
   - PDF or EPUB files

The bot will process the content and send back an audio file.

## Built With

- [python-telegram-bot](https://python-telegram-bot.org/) - Telegram Bot API wrapper
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - OCR engine
- [edge-tts](https://github.com/rany2/edge-tts) - Text to Speech
- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF processing
- [Flask](https://flask.palletsprojects.com/) - Web framework for deployment

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Thanks to Microsoft Edge TTS for providing the text-to-speech service
- Thanks to PaddleOCR team for the excellent OCR engine
- Thanks to all the open-source libraries that made this project possible

## Support

For support, please open an issue in the GitHub repository or contact [@yourusername](https://t.me/yourusername) on Telegram.