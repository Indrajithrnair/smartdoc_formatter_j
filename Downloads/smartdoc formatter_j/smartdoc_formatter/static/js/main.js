document.addEventListener('DOMContentLoaded', () => {
    // General UI Elements
    const themeToggle = document.getElementById('theme-toggle');
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingText = document.getElementById('loading-text');

    // File Upload Elements
    const headerUploadBtn = document.getElementById('upload-btn');
    const fileInput = document.getElementById('file-input'); // Make sure this ID matches your HTML
    const uploadArea = document.getElementById('upload-area');

    // Preview Elements
    const previewContainer = document.getElementById('preview-container');
    const previewContent = document.getElementById('preview-content'); // For displaying document
    const downloadDocBtn = document.getElementById('download-doc'); // In preview toolbar

    // Chat Elements
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    const clearChatBtn = document.getElementById('clear-chat');
    const typingIndicator = document.getElementById('typing-indicator');

    // Modals
    const uploadModal = document.getElementById('upload-modal');
    const uploadProgressFill = document.querySelector('#upload-progress .progress-fill');
    const uploadProgressText = document.querySelector('#upload-progress + .progress-text');
    const errorModal = document.getElementById('error-modal');
    const errorMessageText = document.getElementById('error-message');
    const downloadPromptModal = document.getElementById('download-modal'); // HTML ID is 'download-modal'
    const downloadModalDownloadBtn = document.getElementById('download-btn'); // Button inside the download-modal

    let currentFileId = null;
    let currentFileName = null;

    // --- Utility Functions ---
    function showLoading(text = 'Processing...') {
        if (loadingText) loadingText.textContent = text;
        if (loadingOverlay) loadingOverlay.classList.remove('hidden');
    }

    function hideLoading() {
        if (loadingOverlay) loadingOverlay.classList.add('hidden');
    }

    function showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('hidden');
            modal.setAttribute('aria-hidden', 'false');
        }
    }

    function closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('hidden');
            modal.setAttribute('aria-hidden', 'true');
        }
    }
    window.closeModal = closeModal; // Make global for inline HTML onclick

    function showError(message) {
        if (errorMessageText) errorMessageText.textContent = message;
        showModal('error-modal');
        hideLoading();
    }

    function addChatMessage(type, messageContent) {
        if (!chatMessages) return;
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', type);
        const p = document.createElement('p');
        p.textContent = messageContent; // Use textContent for security
        messageDiv.appendChild(p);
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // --- Theme Toggle ---
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            document.body.classList.toggle('dark-mode');
            const isDarkMode = document.body.classList.contains('dark-mode');
            const icon = themeToggle.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-sun', isDarkMode);
                icon.classList.toggle('fa-moon', !isDarkMode);
            }
            localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
        });
    }

    // Initial theme load (moved here to ensure elements are available)
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        if (themeToggle) {
            const icon = themeToggle.querySelector('i');
            if (icon) {
                icon.classList.remove('fa-moon');
                icon.classList.add('fa-sun');
            }
        }
    } else {
        document.body.classList.remove('dark-mode');
         if (themeToggle) {
            const icon = themeToggle.querySelector('i');
            if (icon) {
                icon.classList.add('fa-moon');
                icon.classList.remove('fa-sun');
            }
        }
    }

    // --- File Upload ---
    if (headerUploadBtn && fileInput) {
        headerUploadBtn.addEventListener('click', () => fileInput.click());
    }
    if (uploadArea && fileInput) {
        uploadArea.addEventListener('click', (e) => {
            if (e.target === uploadArea || e.target.closest('.upload-placeholder')) {
                 fileInput.click();
            }
        });
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                fileInput.files = files; // Assign dropped files to input
                handleFileUpload(files[0]);
            }
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFileUpload(e.target.files[0]);
            }
        });
    }

    async function handleFileUpload(file) {
        if (!file) return;
        const formData = new FormData();
        formData.append('file', file);

        if (uploadModal) showModal('upload-modal');
        if (uploadProgressFill) uploadProgressFill.style.width = '0%';
        if (uploadProgressText) uploadProgressText.textContent = '0%';

        let progressInterval = null;
        try {
            // Basic progress simulation
            let progress = 0;
            if (uploadProgressFill && uploadProgressText) {
                progressInterval = setInterval(() => {
                    progress = Math.min(progress + 10, 90); // Simulate up to 90%
                    uploadProgressFill.style.width = `${progress}%`;
                    uploadProgressText.textContent = `${progress}%`;
                }, 100);
            }

            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData,
            });

            if (progressInterval) clearInterval(progressInterval);
            if (uploadProgressFill) uploadProgressFill.style.width = `100%`;
            if (uploadProgressText) uploadProgressText.textContent = `100%`;
            
            await new Promise(resolve => setTimeout(resolve, 300));
            if (uploadModal) closeModal('upload-modal');

            const data = await response.json();

            if (response.ok) {
                currentFileId = data.file_id;
                currentFileName = data.filename;
                addChatMessage('system', `File "${currentFileName}" uploaded. Ready for instructions.`);
                if (uploadArea) uploadArea.classList.add('hidden');
                if (previewContainer) previewContainer.classList.remove('hidden');
                loadPreview(currentFileId);
            } else {
                showError(data.error || 'File upload failed.');
                if (fileInput) fileInput.value = '';
            }
        } catch (error) {
            if (progressInterval) clearInterval(progressInterval);
            if (uploadModal) closeModal('upload-modal');
            console.error('Upload error:', error);
            showError('An error occurred during file upload.');
            if (fileInput) fileInput.value = '';
        }
    }

    // --- Chat Functionality ---
    if (chatForm) {
        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!chatInput) return;
            const instructionText = chatInput.value.trim();

            if (!instructionText) return;

            if (!currentFileId) {
                showError('Please upload a document first.');
                return;
            }

            addChatMessage('user', instructionText);
            chatInput.value = '';
            if (chatInput.style) chatInput.style.height = 'auto';
            if (typingIndicator) typingIndicator.classList.remove('hidden');

            // No general loading overlay for chat, typing indicator is used.
            // showLoading('Processing instructions...');

            try {
                const response = await fetch('/api/process', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        file_id: currentFileId,
                        instructions: instructionText
                    })
                });

                const data = await response.json();
                if (typingIndicator) typingIndicator.classList.add('hidden');
                // hideLoading();

                if (response.ok) {
                    addChatMessage('ai', data.agent_response || 'Document processed.');
                    if (data.status === 'processed' || data.output_path) {
                        loadPreview(currentFileId); // Reload preview
                        if (downloadPromptModal) showModal('download-modal');
                    }
                } else {
                    const errorMsg = data.error || 'Processing failed.';
                    addChatMessage('ai error', errorMsg);
                    showError(errorMsg);
                }
            } catch (error) {
                if (typingIndicator) typingIndicator.classList.add('hidden');
                // hideLoading();
                console.error('Processing error:', error);
                const errorMsg = 'An error occurred while processing.';
                addChatMessage('ai error', errorMsg);
                showError(errorMsg);
            }
        });
    }

    if (chatInput) {
        chatInput.addEventListener('input', () => {
            // Auto-resize textarea
            if (chatInput.style) {
                chatInput.style.height = 'auto';
                chatInput.style.height = (chatInput.scrollHeight) + 'px';
            }
        });
         chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (chatForm) chatForm.requestSubmit(); // Trigger form submission
            }
        });
    }

    if (clearChatBtn) {
        clearChatBtn.addEventListener('click', () => {
            if (!chatMessages) return;
            // Keep only the first system message or add a new one
            const firstMessage = chatMessages.querySelector('.message.system');
            chatMessages.innerHTML = ''; // Clear existing messages
            if (firstMessage) {
                chatMessages.appendChild(firstMessage.cloneNode(true));
            } else {
                 addChatMessage('system', 'Welcome to SmartDoc Formatter! Upload a document to get started.');
            }
        });
    }

    // --- Document Preview ---
    async function loadPreview(fileId) {
        if (!fileId || !previewContent) return;

        showLoading('Loading preview...');
        previewContent.innerHTML = ''; // Clear previous preview

        try {
            const response = await fetch(`/api/preview/${fileId}`);
            if (!response.ok) {
                const errorData = await response.json().catch(() => null); // Try to get error details
                throw new Error(errorData?.error || `Preview failed with status ${response.status}`);
            }

            const data = await response.json();

            if (data.html) {
                previewContent.innerHTML = data.html;
            } else {
                previewContent.innerHTML = '<p class="error-text">Preview data is empty.</p>';
            }

            if (data.messages && data.messages.length > 0) {
                console.warn('Document conversion messages:', data.messages);
                // Optionally, display these messages to the user in a non-intrusive way
                // For example, append them to a specific log area or a small notification
                const messageNote = document.createElement('p');
                messageNote.className = 'preview-messages-note';
                messageNote.textContent = `Note: ${data.messages.join(', ')}`;
                // previewContent.appendChild(messageNote); // Or add to another dedicated spot
            }

            // Ensure preview container is visible and upload area is hidden
            if (uploadArea) uploadArea.classList.add('hidden');
            if (previewContainer) previewContainer.classList.remove('hidden');

        } catch (error) {
            console.error('Preview loading error:', error);
            previewContent.innerHTML = `<p class="error-text">Could not load preview: ${error.message}</p>`;
            // showError(`Could not load preview: ${error.message}`); // This might be too intrusive
        } finally {
            hideLoading();
        }
    }

    // --- Download Functionality ---
    if (downloadDocBtn) { // Download button in preview toolbar
        downloadDocBtn.addEventListener('click', () => {
            if (currentFileId) {
                window.location.href = `/api/download/${currentFileId}`;
            } else {
                showError('No active document to download.');
            }
        });
    }

    if (downloadModalDownloadBtn) { // Download button in the download modal (assuming ID is 'download-btn' as per HTML)
        // Check if the element exists and its ID is indeed 'download-btn' as used in variable assignment
        const actualDownloadModalBtn = document.getElementById('download-btn');
        if (actualDownloadModalBtn && downloadModalDownloadBtn === actualDownloadModalBtn) {
            downloadModalDownloadBtn.addEventListener('click', () => {
                if (currentFileId) {
                    window.location.href = `/api/download/${currentFileId}`;
                    closeModal('download-modal');
                } else {
                    showError('No active document to download.');
                    closeModal('download-modal');
                }
            });
        } else if (downloadModalDownloadBtn && actualDownloadModalBtn !== downloadModalDownloadBtn) {
            // This case implies downloadModalDownloadBtn might be something else or misconfigured.
            // It's safer to re-fetch by ID if there's a doubt, or ensure var name matches the specific button.
            // For now, this indicates a potential mismatch if the `else if` is hit.
            console.warn("downloadModalDownloadBtn variable might not be the actual button with ID 'download-btn' from the modal.");
        }
    }


    // Initial welcome message
    // Moved earlier in the script after addChatMessage is defined.
    // addChatMessage('system', 'Welcome to SmartDoc Formatter! Upload a document or drag and drop it to get started.');
}); 