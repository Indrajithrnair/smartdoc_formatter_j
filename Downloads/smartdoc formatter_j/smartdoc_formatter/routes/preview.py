from flask import Blueprint, jsonify, current_app, session
import mammoth
import bleach
import os

from utils.helpers import get_file_path

preview_bp = Blueprint('preview', __name__)

# Configure bleach for safe HTML
ALLOWED_TAGS = [
    'p', 'br', 'b', 'i', 'u', 'em', 'strong', 'a', 'h1', 'h2', 'h3',
    'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'blockquote', 'pre', 'code',
    'hr', 'div', 'span', 'table', 'thead', 'tbody', 'tr', 'th', 'td'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title'],
    '*': ['class', 'style']
}

@preview_bp.route('/preview/<file_id>', methods=['GET'])
def preview_document(file_id):
    """Generate HTML preview of the document."""
    # Find file info in session
    file_info = next((f for f in session['files'] if f['id'] == file_id), None)
    if not file_info:
        return jsonify({'error': 'File not found'}), 404

    try:
        filepath = get_file_path(file_info['filename'], current_app)
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found on server'}), 404

        # Convert DOCX to HTML
        with open(filepath, 'rb') as docx_file:
            result = mammoth.convert_to_html(docx_file)
            html = result.value
            messages = result.messages  # Contains any warnings during conversion

        # Sanitize HTML
        clean_html = bleach.clean(
            html,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            strip=True
        )

        # Log any conversion messages
        if messages:
            current_app.logger.info(f"Document conversion messages for {file_id}: {messages}")

        return jsonify({
            'html': clean_html,
            'messages': [str(msg) for msg in messages]
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error generating preview: {str(e)}")
        return jsonify({'error': 'Error generating document preview'}), 500 