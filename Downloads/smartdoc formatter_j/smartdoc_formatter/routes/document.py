from flask import Blueprint, request, jsonify, current_app, session, send_file
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import datetime

from services.document_processor import DocumentProcessor

from services.word_handler import DocumentHandler
from utils.helpers import allowed_file, get_file_path

document_bp = Blueprint('document', __name__)
processor = DocumentProcessor()
word_handler = DocumentHandler()

@document_bp.route('/', methods=['GET'])
def index():
    """Serve the main interface."""
    return jsonify({
        "status": "success",
        "message": "SmartDoc Formatter API",
        "version": "1.0.0"
    })

@document_bp.route('/upload', methods=['POST'])
def upload_document():
    """Handle document upload."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if not allowed_file(file.filename, current_app):
        return jsonify({'error': 'Invalid file type. Only .docx files are allowed'}), 400

    try:
        # Generate unique file ID and secure filename
        file_id = str(uuid.uuid4())
        original_filename = secure_filename(file.filename)
        filename = f"{file_id}_{original_filename}"
        filepath = get_file_path(filename, current_app)

        # Save the file
        file.save(filepath)

        # Store file info in session
        file_info = {
            'id': file_id,
            'original_name': original_filename,
            'filename': filename,
            'uploaded_at': datetime.utcnow().isoformat(),
            'status': 'uploaded'
        }
        session['files'].append(file_info)
        session.modified = True

        current_app.logger.info(f"File uploaded successfully: {filename}")
        return jsonify({
            'message': 'File uploaded successfully',
            'file_id': file_id,
            'filename': original_filename
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error uploading file: {str(e)}")
        return jsonify({'error': 'Error uploading file'}), 500

@document_bp.route('/process', methods=['POST'])
def process_document():
    """Process document with AI instructions."""
    data = request.get_json()
    if not data or 'file_id' not in data:
        return jsonify({'error': 'No file ID provided'}), 400

    file_id = data['file_id']
    instructions = data.get('instructions', '')

    # Find file info in session
    file_info = next((f for f in session['files'] if f['id'] == file_id), None)
    if not file_info:
        return jsonify({'error': 'File not found'}), 404

    try:
        filepath = get_file_path(file_info['filename'], current_app)
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found on server'}), 404

        # Process the document
        result = processor.process_document(filepath)
        if result['status'] == 'error':
            raise Exception(result['message'])

        # Update file status
        file_info['status'] = 'processed'
        file_info['processed_at'] = datetime.utcnow().isoformat()
        session.modified = True

        return jsonify({
            'message': 'Document processed successfully',
            'file_id': file_id,
            'status': 'processed'
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error processing document: {str(e)}")
        return jsonify({'error': f'Error processing document: {str(e)}'}), 500

@document_bp.route('/download/<file_id>', methods=['GET'])
def download_document(file_id):
    """Download processed document."""
    # Find file info in session
    file_info = next((f for f in session['files'] if f['id'] == file_id), None)
    if not file_info:
        return jsonify({'error': 'File not found'}), 404

    try:
        filepath = get_file_path(file_info['filename'], current_app)
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found on server'}), 404

        return send_file(
            filepath,
            as_attachment=True,
            download_name=file_info['original_name'],
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

    except Exception as e:
        current_app.logger.error(f"Error downloading document: {str(e)}")
        return jsonify({'error': 'Error downloading document'}), 500 