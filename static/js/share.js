/**
 * WONTECH Share Manager
 * Handles sharing reports via email, SMS, or download
 */

class ShareManager {
    constructor() {
        this.currentFile = null;
        this.currentFileName = null;
        this.currentFileType = 'text/csv';
        this.serviceStatus = null;
        this.init();
    }

    init() {
        // Check service status on load
        this.checkServiceStatus();
        // Inject modal if not present
        if (!document.getElementById('shareModal')) {
            this.injectModal();
        }
    }

    async checkServiceStatus() {
        try {
            const response = await fetch('/api/share/status');
            if (response.ok) {
                this.serviceStatus = await response.json();
            }
        } catch (e) {
            console.log('Share service status check failed');
        }
    }

    injectModal() {
        const modalHTML = `
        <div class="share-modal-overlay" id="shareModal">
            <div class="share-modal">
                <div class="share-modal-header">
                    <h3>Share Report</h3>
                    <button class="share-modal-close" onclick="shareManager.closeModal()">&times;</button>
                </div>

                <div class="share-modal-body">
                    <!-- File Preview -->
                    <div class="share-file-preview">
                        <span class="share-file-icon">📄</span>
                        <div class="share-file-info">
                            <span class="share-file-name" id="shareFileName">report.csv</span>
                            <span class="share-file-size" id="shareFileSize"></span>
                        </div>
                    </div>

                    <!-- Share Options -->
                    <div class="share-options" id="shareOptions">
                        <button class="share-option-btn" onclick="shareManager.showEmailForm()">
                            <span class="share-option-icon">📧</span>
                            <span class="share-option-label">Email</span>
                            <span class="share-option-desc">Send as attachment</span>
                        </button>
                        <button class="share-option-btn" onclick="shareManager.showTextForm()">
                            <span class="share-option-icon">💬</span>
                            <span class="share-option-label">Text</span>
                            <span class="share-option-desc">Send download link</span>
                        </button>
                        <button class="share-option-btn" onclick="shareManager.downloadFile()">
                            <span class="share-option-icon">💾</span>
                            <span class="share-option-label">Download</span>
                            <span class="share-option-desc">Save to device</span>
                        </button>
                    </div>

                    <!-- Email Form -->
                    <div class="share-form" id="shareEmailForm" style="display: none;">
                        <div class="share-form-field">
                            <label>Recipient Email</label>
                            <input type="email" id="shareEmail" placeholder="recipient@email.com" required>
                        </div>
                        <div class="share-form-field">
                            <label>Subject</label>
                            <input type="text" id="shareEmailSubject" placeholder="Your Report from WONTECH">
                        </div>
                        <div class="share-form-field">
                            <label>Message (optional)</label>
                            <textarea id="shareEmailMessage" placeholder="Add a personal message..." rows="3"></textarea>
                        </div>
                        <div class="share-form-actions">
                            <button class="share-back-btn" onclick="shareManager.showOptions()">← Back</button>
                            <button class="share-send-btn" id="emailSendBtn" onclick="shareManager.sendEmail()">
                                <span id="emailSendText">Send Email</span>
                                <span id="emailSendSpinner" class="share-spinner" style="display:none;"></span>
                            </button>
                        </div>
                    </div>

                    <!-- Text Form -->
                    <div class="share-form" id="shareTextForm" style="display: none;">
                        <div class="share-form-field">
                            <label>Phone Number</label>
                            <input type="tel" id="sharePhone" placeholder="(555) 555-5555" required>
                        </div>
                        <div class="share-form-field">
                            <label>Message (optional)</label>
                            <textarea id="shareTextMessage" placeholder="Your report is ready!" rows="2"></textarea>
                        </div>
                        <div class="share-form-note">
                            A secure download link will be included in the text message. Link expires in 24 hours.
                        </div>
                        <div class="share-form-actions">
                            <button class="share-back-btn" onclick="shareManager.showOptions()">← Back</button>
                            <button class="share-send-btn" id="textSendBtn" onclick="shareManager.sendText()">
                                <span id="textSendText">Send Text</span>
                                <span id="textSendSpinner" class="share-spinner" style="display:none;"></span>
                            </button>
                        </div>
                    </div>

                    <!-- Success State -->
                    <div class="share-success" id="shareSuccess" style="display: none;">
                        <div class="share-success-icon">✓</div>
                        <div class="share-success-title">Sent Successfully!</div>
                        <div class="share-success-message" id="shareSuccessMessage"></div>
                        <button class="share-done-btn" onclick="shareManager.closeModal()">Done</button>
                    </div>
                </div>
            </div>
        </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }

    // Open share modal with file data
    open(fileData, fileName, fileType = 'text/csv') {
        this.currentFile = fileData;
        this.currentFileName = fileName;
        this.currentFileType = fileType;

        // Update preview
        document.getElementById('shareFileName').textContent = fileName;
        const sizeKB = Math.round(new Blob([fileData]).size / 1024);
        document.getElementById('shareFileSize').textContent = `${sizeKB} KB`;

        // Reset form
        this.showOptions();
        document.getElementById('shareEmail').value = '';
        document.getElementById('shareEmailSubject').value = `Report: ${fileName}`;
        document.getElementById('shareEmailMessage').value = '';
        document.getElementById('sharePhone').value = '';
        document.getElementById('shareTextMessage').value = '';

        // Show modal
        document.getElementById('shareModal').classList.add('visible');
    }

    closeModal() {
        document.getElementById('shareModal').classList.remove('visible');
        this.currentFile = null;
        this.currentFileName = null;
    }

    showOptions() {
        document.getElementById('shareOptions').style.display = 'flex';
        document.getElementById('shareEmailForm').style.display = 'none';
        document.getElementById('shareTextForm').style.display = 'none';
        document.getElementById('shareSuccess').style.display = 'none';
    }

    showEmailForm() {
        document.getElementById('shareOptions').style.display = 'none';
        document.getElementById('shareEmailForm').style.display = 'block';
        document.getElementById('shareEmail').focus();
    }

    showTextForm() {
        document.getElementById('shareOptions').style.display = 'none';
        document.getElementById('shareTextForm').style.display = 'block';
        document.getElementById('sharePhone').focus();
    }

    showSuccess(message) {
        document.getElementById('shareOptions').style.display = 'none';
        document.getElementById('shareEmailForm').style.display = 'none';
        document.getElementById('shareTextForm').style.display = 'none';
        document.getElementById('shareSuccess').style.display = 'block';
        document.getElementById('shareSuccessMessage').textContent = message;
    }

    // Convert file data to base64
    getBase64Data() {
        return btoa(unescape(encodeURIComponent(this.currentFile)));
    }

    // Send email
    async sendEmail() {
        const email = document.getElementById('shareEmail').value.trim();
        if (!email) {
            alert('Please enter an email address');
            return;
        }

        const btn = document.getElementById('emailSendBtn');
        const text = document.getElementById('emailSendText');
        const spinner = document.getElementById('emailSendSpinner');

        btn.disabled = true;
        text.style.display = 'none';
        spinner.style.display = 'inline-block';

        try {
            const response = await fetch('/api/share/email', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    to: email,
                    subject: document.getElementById('shareEmailSubject').value || `Report: ${this.currentFileName}`,
                    message: document.getElementById('shareEmailMessage').value,
                    file_data: this.getBase64Data(),
                    file_name: this.currentFileName,
                    file_type: this.currentFileType
                })
            });

            const result = await response.json();

            if (response.ok) {
                this.showSuccess(`Email sent to ${email}`);
            } else {
                alert(result.error || 'Failed to send email');
            }
        } catch (error) {
            alert('Failed to send email: ' + error.message);
        } finally {
            btn.disabled = false;
            text.style.display = 'inline';
            spinner.style.display = 'none';
        }
    }

    // Send text
    async sendText() {
        const phone = document.getElementById('sharePhone').value.trim();
        if (!phone) {
            alert('Please enter a phone number');
            return;
        }

        const btn = document.getElementById('textSendBtn');
        const text = document.getElementById('textSendText');
        const spinner = document.getElementById('textSendSpinner');

        btn.disabled = true;
        text.style.display = 'none';
        spinner.style.display = 'inline-block';

        try {
            const response = await fetch('/api/share/text', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    to: phone,
                    message: document.getElementById('shareTextMessage').value || 'Your report from WONTECH is ready.',
                    file_data: this.getBase64Data(),
                    file_name: this.currentFileName,
                    file_type: this.currentFileType
                })
            });

            const result = await response.json();

            if (response.ok) {
                this.showSuccess(`Text sent to ${phone}`);
            } else {
                alert(result.error || 'Failed to send text');
            }
        } catch (error) {
            alert('Failed to send text: ' + error.message);
        } finally {
            btn.disabled = false;
            text.style.display = 'inline';
            spinner.style.display = 'none';
        }
    }

    // Direct download
    downloadFile() {
        const blob = new Blob([this.currentFile], { type: this.currentFileType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = this.currentFileName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        this.closeModal();
    }
}

// Global instance
const shareManager = new ShareManager();

// Helper function to share CSV data
function shareCSV(csvContent, fileName) {
    shareManager.open(csvContent, fileName, 'text/csv');
}

// Helper function to share any file
function shareFile(content, fileName, fileType) {
    shareManager.open(content, fileName, fileType);
}
