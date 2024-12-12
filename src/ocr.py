import io
import os
import tempfile
from PIL import Image
from paddleocr import PaddleOCR
from .config import OCR_LANG
from .utils import is_chinese

class OCRProcessor:
    def __init__(self):
        self.paddleocr = PaddleOCR(
            use_angle_cls=True,
            lang=OCR_LANG,
            use_gpu=False,
            show_log=False,
            use_space_char=True
        )

    def process_image(self, photo_bytes: bytes) -> str:
        """Convert photo to text using OCR."""
        temp_image_path = None
        try:
            temp_dir = tempfile.gettempdir()
            temp_image_path = os.path.join(temp_dir, 'temp_image.png')
            image_bytes = io.BytesIO(photo_bytes)
            image = Image.open(image_bytes)
            image.save(temp_image_path)
            
            print('Using PaddleOCR')
            result = self.paddleocr.ocr(temp_image_path)
            
            if not result or not result[0]:
                return ''
            
            text_list = [line[1][0] for line in result[0]]
            full_text = ''.join(text_list)
            
            cleaned_text = full_text  # to do: add cleaning logic         
                
            return cleaned_text.strip() if cleaned_text.strip() else ''
            
        except Exception as e:
            print(f"Error in OCR processing: {str(e)}")
            return "Sorry, I couldn't process this image. Please try again with a clearer image."
        finally:
            if temp_image_path and os.path.exists(temp_image_path):
                os.remove(temp_image_path) 