import sys
import os
import cv2
import numpy as np
import logging
from PIL import Image
import io
import easyocr

# Configure logging to output to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Add project root to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.config import USE_EASY_OCR, OCR_LANG
from src.OnnxOCR.onnxocr.onnx_paddleocr import ONNXPaddleOcr

class OCRService:
    def __init__(self):
        try:
            # Initialize PaddleOCR for Chinese
            base_path = os.path.join(current_dir, '../OnnxOCR/onnxocr/models')
            det_path = os.path.join(base_path, 'ppocrv4/det/det.onnx')
            rec_path = os.path.join(base_path, 'ppocrv4/rec/rec.onnx')
            cls_path = os.path.join(base_path, 'ppocrv4/cls/cls.onnx')
            dict_path = os.path.join(base_path, 'ch_ppocr_server_v2.0/ppocr_keys_v1.txt')
            
            self._check_model_files(det_path, rec_path, cls_path, dict_path)
            
            self.paddle_ocr = ONNXPaddleOcr(
                det_model_dir=det_path,
                rec_model_dir=rec_path,
                cls_model_dir=cls_path,
                rec_char_dict_path=dict_path,
                use_angle_cls=True,
                use_gpu=False
            )

            # Initialize EasyOCR for other languages
            if USE_EASY_OCR:
                self.easy_ocr = easyocr.Reader([OCR_LANG])
            
            logger.info("OCR services initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize OCR services: {str(e)}")
            raise

    def _check_model_files(self, det_path, rec_path, cls_path, dict_path):
        """Check if all required model files exist"""
        files_to_check = {
            "Detection model": det_path,
            "Recognition model": rec_path,
            "Classification model": cls_path,
            "Dictionary file": dict_path
        }
        
        for name, path in files_to_check.items():
            if not os.path.exists(path):
                raise FileNotFoundError(f"{name} not found at: {path}")
            logger.info(f"{name} found at: {path}")

    def _convert_to_cv2_image(self, image_data):
        """Convert different image formats to CV2 format"""
        try:
            if isinstance(image_data, (bytes, bytearray)):
                # Handle byte stream or byte array
                nparr = np.frombuffer(image_data, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if image is None:
                    # Try processing with PIL
                    try:
                        pil_image = Image.open(io.BytesIO(image_data))
                        image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                    except Exception as pil_error:
                        logger.error(f"Failed to decode image with PIL: {str(pil_error)}")
                        raise ValueError("Failed to decode image bytes")
                return image
                
            elif isinstance(image_data, str):
                # If it's a file path
                image = cv2.imread(image_data)
                if image is None:
                    raise ValueError(f"Failed to load image from path: {image_data}")
                return image
                
            elif isinstance(image_data, np.ndarray):
                # If it's already a numpy array, ensure correct format
                if len(image_data.shape) == 2:  # Grayscale image
                    image = cv2.cvtColor(image_data, cv2.COLOR_GRAY2BGR)
                elif len(image_data.shape) == 3 and image_data.shape[2] == 3:  # RGB image
                    image = image_data
                else:
                    raise ValueError(f"Unsupported numpy array shape: {image_data.shape}")
                return image
                
            elif isinstance(image_data, Image.Image):
                # If it's a PIL image
                image = cv2.cvtColor(np.array(image_data), cv2.COLOR_RGB2BGR)
                return image
                
            else:
                raise ValueError(f"Unsupported image type: {type(image_data)}")
                
        except Exception as e:
            logger.error(f"Error converting image: {str(e)}")
            raise ValueError(f"Image conversion failed: {str(e)}")

    def process_image(self, image_data):
        """Process image and return OCR results"""
        try:
            # Convert image format
            image = self._convert_to_cv2_image(image_data)
            
            if USE_EASY_OCR:
                # Use EasyOCR for non-Chinese languages
                logger.info(f"Using EasyOCR with language: {OCR_LANG}")
                results = self.easy_ocr.readtext(image)
                ocr_results = []
                for result in results:
                    box, text, confidence = result
                    ocr_results.append({
                        'box': box,
                        'text': text,
                        'confidence': float(confidence)
                    })
            else:
                # Use PaddleOCR for Chinese
                logger.info("Using PaddleOCR for Chinese text")
                result = self.paddle_ocr.ocr(image)
                if not result or not result[0]:
                    return []
                    
                ocr_results = []
                for line in result[0]:
                    box = line[0]
                    text = line[1][0]
                    confidence = line[1][1]
                    
                    ocr_results.append({
                        'box': box,
                        'text': text,
                        'confidence': float(confidence)
                    })
            
            logger.info(f"Successfully processed image, found {len(ocr_results)} text regions")
            return ocr_results

        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            raise 