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
        # Pass instructions to the processor
        result = processor.process_document(filepath, instructions=instructions)
        if result['status'] == 'error':
            raise Exception(result['message'])

        # Update file status and filename to the processed version
        file_info['status'] = 'processed'
        file_info['processed_at'] = datetime.utcnow().isoformat()

        # The processor saves the file with '_processed.docx'
        # output_path will be like 'uploads/uuid_original_processed.docx'
        # We need to store the new base filename in the session.
        if result.get('output_path'):
            new_filename = os.path.basename(result['output_path'])
            # Log the change for debugging
            current_app.logger.info(f"Original filename in session: {file_info['filename']}, New filename: {new_filename}")
            file_info['filename'] = new_filename
        else:
            # This case should ideally not happen if processing is successful and output_path is always returned
            current_app.logger.warning(f"No output_path returned from processor for file_id {file_id}")
            # Fallback or specific handling might be needed if output_path is not guaranteed
            # For now, we'll assume it's an issue if not present and rely on original filename if it happens

        session.modified = True

        return jsonify({
            'message': 'Document processed successfully',
            'file_id': file_id,
            'status': 'processed',
            'agent_response': result.get('agent_response', 'Processing complete.'), # Pass through agent response
            'output_path': result.get('output_path') # For frontend confirmation if needed
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