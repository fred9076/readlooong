import os
import tempfile
import edge_tts
from .config import VOICE
from .utils import create_safe_filename

async def convert_to_audio(text: str) -> tuple[bool, str]:
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