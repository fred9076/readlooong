import os
import tempfile
import edge_tts
from .config import VOICE
from .utils import create_safe_filename

async def convert_to_audio(text: str, progress=None) -> tuple[bool, str]:
    """Convert text to audio using edge-tts."""
    try:
        # Skip empty text
        if not text or not text.strip():
            return False, "Empty text provided"

        temp_dir = tempfile.gettempdir()
        filename = create_safe_filename(text)
        temp_audio_path = os.path.join(temp_dir, filename)
        
        print(f'Using voice: {VOICE} for text: {text[:50]}...{text[-50:]}')
        communicate = edge_tts.Communicate(text, VOICE)
        
        try:
            # First generate the audio stream
            chars_processed = 0
            audio_data = bytearray()
            
            async for event in communicate.stream():
                if event["type"] == "audio":
                    audio_data.extend(event["data"])
                elif event["type"] == "word":
                    chars_processed += len(event["text"])
                    if progress:
                        progress.update(chars_processed)
            
            # Then save the audio data
            if audio_data:
                with open(temp_audio_path, "wb") as audio_file:
                    audio_file.write(audio_data)
                return True, temp_audio_path
            else:
                raise Exception("No audio data generated")

        except Exception as stream_error:
            print(f"Streaming error: {str(stream_error)}")
            # Try direct save method as fallback
            try:
                await communicate.save(temp_audio_path)
                return True, temp_audio_path
            except Exception as save_error:
                print(f"Save error: {str(save_error)}")
                raise save_error

    except Exception as e:
        print(f"Error in text-to-speech conversion: {str(e)}")
        error_msg = str(e)
        if "Status code: 429" in error_msg:
            return False, "Service is busy. Please try again in a few minutes."
        elif "Status code: 413" in error_msg:
            return False, "Text is too long. Please try with a shorter section."
        else:
            return False, f"Conversion error: {error_msg}" 