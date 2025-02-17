from flask import Blueprint, request, jsonify
from services.ocr_service import OCRService
import logging
import traceback

logger = logging.getLogger(__name__)
ocr_bp = Blueprint('ocr', __name__)
ocr_service = OCRService()

@ocr_bp.route('/ocr', methods=['POST'])
def process_image():
    try:
        # Check request
        if not request.files:
            return jsonify({
                'success': False,
                'error': 'No files in request'
            }), 400

        if 'image' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No image field in request'
            }), 400
            
        file = request.files['image']
        if not file.filename:
            return jsonify({
                'success': False,
                'error': 'No selected file'
            }), 400

        # Read image data
        try:
            file_bytes = file.read()
            if not file_bytes:
                raise ValueError("Empty file")
        except Exception as e:
            logger.error(f"Error reading file: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Failed to read image file'
            }), 400
        
        # Process OCR
        try:
            results = ocr_service.process_image(file_bytes)
        except Exception as e:
            logger.error(f"OCR processing error: {str(e)}\n{traceback.format_exc()}")
            return jsonify({
                'success': False,
                'error': 'OCR processing failed'
            }), 500
        
        return jsonify({
            'success': True,
            'data': results
        })
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500 