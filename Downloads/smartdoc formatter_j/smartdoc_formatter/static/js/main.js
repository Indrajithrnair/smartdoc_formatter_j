document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('upload-form');
    const fileInput = document.getElementById('document');
    const fileLabel = document.querySelector('.file-label');
    const statusDiv = document.getElementById('status');

    fileInput.addEventListener('change', (e) => {
        const fileName = e.target.files[0]?.name || 'Choose a file';
        fileLabel.textContent = fileName;
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(form);
        
        if (!fileInput.files[0]) {
            showStatus('Please select a file first', 'error');
            return;
        }

        try {
            showStatus('Uploading file...', '');
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            
            if (response.ok) {
                showStatus(data.message, 'success');
            } else {
                showStatus(data.error, 'error');
            }
        } catch (error) {
            showStatus('An error occurred while uploading the file', 'error');
            console.error('Upload error:', error);
        }
    });

    function showStatus(message, type) {
        statusDiv.textContent = message;
        statusDiv.className = 'status-message';
        if (type) {
            statusDiv.classList.add(type);
        }
    }
}); 