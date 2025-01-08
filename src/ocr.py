import logging
import numpy as np
from PIL import Image
import io
from .services.ocr_service import OCRService

logger = logging.getLogger(__name__)

class OCRProcessor:
    def __init__(self):
        """初始化OCR处理器"""
        try:
            self.ocr_service = OCRService()
            logger.info("OCR processor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OCR processor: {str(e)}")
            raise

    def process_image(self, image_data):
        """处理图像并返回OCR结果"""
        try:
            # 处理图像
            results = self.ocr_service.process_image(image_data)
            
            # 提取文本
            if not results:
                return ""
                
            # 按照y坐标排序，实现自上而下的阅读顺序
            sorted_results = sorted(results, key=lambda x: x['box'][0][1])
            
            # 组合所有文本
            text = '\n'.join(result['text'] for result in sorted_results)
            
            return text

        except Exception as e:
            logger.error(f"Error in OCR processing: {str(e)}")
            return "Sorry, I couldn't process this image. Please try again with a clearer image."

    def process_pdf_page(self, image):
        """处理PDF页面图像"""
        try:
            # 确保图像是numpy数组格式
            if isinstance(image, Image.Image):
                image = np.array(image)
            
            # 处理图像
            results = self.ocr_service.process_image(image)
            
            # 提取并组合文本
            if not results:
                return ""
                
            sorted_results = sorted(results, key=lambda x: x['box'][0][1])
            text = '\n'.join(result['text'] for result in sorted_results)
            
            return text

        except Exception as e:
            logger.error(f"Error in PDF page OCR processing: {str(e)}")
            return "Sorry, I couldn't process this page. Please try again with a clearer PDF." 