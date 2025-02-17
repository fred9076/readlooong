import os
import cv2
import logging

# Set logging level
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ocr():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.join(current_dir, 'OnnxOCR/onnxocr/models')
        
        # Print path information
        logger.info(f"Current directory: {current_dir}")
        logger.info(f"Base path: {base_path}")
        
        # Check if model files exist
        det_path = os.path.join(base_path, 'ppocrv4/det/det.onnx')
        rec_path = os.path.join(base_path, 'ppocrv4/rec/rec.onnx')
        cls_path = os.path.join(base_path, 'ppocrv4/cls/cls.onnx')
        dict_path = os.path.join(base_path, 'ch_ppocr_server_v2.0/ppocr_keys_v1.txt')
        
        logger.info(f"Checking model files:")
        logger.info(f"Det model exists: {os.path.exists(det_path)}")
        logger.info(f"Rec model exists: {os.path.exists(rec_path)}")
        logger.info(f"Cls model exists: {os.path.exists(cls_path)}")
        logger.info(f"Dict file exists: {os.path.exists(dict_path)}")
        
        from OnnxOCR.onnxocr.onnx_paddleocr import ONNXPaddleOcr
        
        # Initialize model
        ocr = ONNXPaddleOcr(
            det_model_dir=det_path,
            rec_model_dir=rec_path,
            cls_model_dir=cls_path,
            rec_char_dict_path=dict_path,
            use_angle_cls=True,
            use_gpu=False
        )
        
        # Test image path
        test_image_path = os.path.join(current_dir, 'OnnxOCR/onnxocr/test_images/1.jpg')
        logger.info(f"Test image exists: {os.path.exists(test_image_path)}")
        
        img = cv2.imread(test_image_path)
        if img is None:
            logger.error("Failed to load test image")
            return
            
        result = ocr.ocr(img)
        print("OCR Result:", result)
        
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}", exc_info=True)

if __name__ == "__main__":
    test_ocr() 