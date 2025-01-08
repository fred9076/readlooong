import logging
import numpy as np
from PIL import Image
import io
from .services.ocr_service import OCRService

logger = logging.getLogger(__name__)

class OCRProcessor:
    def __init__(self):
        """Initialize OCR processor"""
        try:
            self.ocr_service = OCRService()
            logger.info("OCR processor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OCR processor: {str(e)}")
            raise

    def process_image(self, image_data):
        """Process image and return OCR results"""
        try:
            # Process image
            results = self.ocr_service.process_image(image_data)
            
            # Extract text
            if not results:
                return ""
                
            # Sort results by y-coordinate for top-to-bottom reading order
            sorted_results = sorted(results, key=lambda x: x['box'][0][1])
            
            # Combine all text
            text = '\n'.join(result['text'] for result in sorted_results)
            
            return text

        except Exception as e:
            logger.error(f"Error in OCR processing: {str(e)}")
            return "Sorry, I couldn't process this image. Please try again with a clearer image."

    def process_pdf_page(self, image):
        """Process PDF page image"""
        try:
            # Ensure image is numpy array
            if isinstance(image, Image.Image):
                image = np.array(image)
            
            # Process image
            results = self.ocr_service.process_image(image)
            
            # Extract and combine text
            if not results:
                return ""
                
            sorted_results = sorted(results, key=lambda x: x['box'][0][1])
            text = '\n'.join(result['text'] for result in sorted_results)
            
            return text

        except Exception as e:
            logger.error(f"Error in PDF page OCR processing: {str(e)}")
            return "Sorry, I couldn't process this page. Please try again with a clearer PDF." 