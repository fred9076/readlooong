import sys
import os
import cv2
import numpy as np
import logging
from PIL import Image
import io

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.OnnxOCR.onnxocr.onnx_paddleocr import ONNXPaddleOcr

logger = logging.getLogger(__name__)

class OCRService:
    def __init__(self):
        try:
            # 获取当前文件所在目录
            base_path = os.path.join(current_dir, '../OnnxOCR/onnxocr/models')
            
            # 构建模型路径
            det_path = os.path.join(base_path, 'ppocrv4/det/det.onnx')
            rec_path = os.path.join(base_path, 'ppocrv4/rec/rec.onnx')
            cls_path = os.path.join(base_path, 'ppocrv4/cls/cls.onnx')
            dict_path = os.path.join(base_path, 'ch_ppocr_server_v2.0/ppocr_keys_v1.txt')
            
            # 检查模型文件
            self._check_model_files(det_path, rec_path, cls_path, dict_path)
            
            # 初始化OnnxOCR模型
            self.ocr = ONNXPaddleOcr(
                det_model_dir=det_path,
                rec_model_dir=rec_path,
                cls_model_dir=cls_path,
                rec_char_dict_path=dict_path,
                use_angle_cls=True,
                use_gpu=False
            )
            logger.info("OnnxOCR model initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize OnnxOCR model: {str(e)}")
            raise

    def _check_model_files(self, det_path, rec_path, cls_path, dict_path):
        """检查所有必需的模型文件是否存在"""
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
        """将不同格式的图像数据转换为CV2格式"""
        try:
            if isinstance(image_data, (bytes, bytearray)):
                # 处理字节流或字节数组
                nparr = np.frombuffer(image_data, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if image is None:
                    # 尝试通过PIL处理
                    try:
                        pil_image = Image.open(io.BytesIO(image_data))
                        image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                    except Exception as pil_error:
                        logger.error(f"Failed to decode image with PIL: {str(pil_error)}")
                        raise ValueError("Failed to decode image bytes")
                return image
                
            elif isinstance(image_data, str):
                # 如果是文件路径
                image = cv2.imread(image_data)
                if image is None:
                    raise ValueError(f"Failed to load image from path: {image_data}")
                return image
                
            elif isinstance(image_data, np.ndarray):
                # 如果已经是numpy数组，确保是正确的格式
                if len(image_data.shape) == 2:  # 灰度图像
                    image = cv2.cvtColor(image_data, cv2.COLOR_GRAY2BGR)
                elif len(image_data.shape) == 3 and image_data.shape[2] == 3:  # RGB图像
                    image = image_data
                else:
                    raise ValueError(f"Unsupported numpy array shape: {image_data.shape}")
                return image
                
            elif isinstance(image_data, Image.Image):
                # 如果是PIL图像
                image = cv2.cvtColor(np.array(image_data), cv2.COLOR_RGB2BGR)
                return image
                
            else:
                raise ValueError(f"Unsupported image type: {type(image_data)}")
                
        except Exception as e:
            logger.error(f"Error converting image: {str(e)}")
            raise ValueError(f"Image conversion failed: {str(e)}")

    def process_image(self, image_data):
        """处理图像并返回OCR结果"""
        try:
            # 转换图像格式
            image = self._convert_to_cv2_image(image_data)
            
            # 执行OCR识别
            result = self.ocr.ocr(image)
            
            # 处理结果
            if not result or not result[0]:
                return []
                
            ocr_results = []
            for line in result[0]:
                box = line[0]  # 文本框坐标
                text = line[1][0]  # 识别的文本
                confidence = line[1][1]  # 置信度
                
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