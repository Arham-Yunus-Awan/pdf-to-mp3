class PDFConverter {
    constructor() {
        this.selectedFile = null;
        this.initializeElements();
        this.bindEvents();
    }

    initializeElements() {
        this.uploadArea = document.getElementById('uploadArea');
        this.fileInput = document.getElementById('fileInput');
        this.fileInfo = document.getElementById('fileInfo');
        this.fileName = document.getElementById('fileName');
        this.fileSize = document.getElementById('fileSize');
        this.convertBtn = document.getElementById('convertBtn');
        this.progressContainer = document.getElementById('progressContainer');
        this.progressFill = document.getElementById('progressFill');
        this.progressText = document.getElementById('progressText');
        this.resultContainer = document.getElementById('resultContainer');
        this.resultText = document.getElementById('resultText');
        this.downloadBtn = document.getElementById('downloadBtn');
        this.resetBtn = document.getElementById('resetBtn');
        this.languageSelect = document.getElementById('languageSelect');
        this.alertBox = document.getElementById('alertBox');
    }

    bindEvents() {
        // File input events
        this.uploadArea.addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));

        // Drag and drop events
        this.uploadArea.addEventListener('dragover', (e) => this.handleDragOver(e));
        this.uploadArea.addEventListener('dragleave', (e) => this.handleDragLeave(e));
        this.uploadArea.addEventListener('drop', (e) => this.handleDrop(e));

        // Button events
        this.convertBtn.addEventListener('click', () => this.convertFile());
        this.resetBtn.addEventListener('click', () => this.reset());

        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            document.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });
    }

    handleDragOver(e) {
        e.preventDefault();
        this.uploadArea.classList.add('dragover');
    }

    handleDragLeave(e) {
        e.preventDefault();
        this.uploadArea.classList.remove('dragover');
    }

    handleDrop(e) {
        e.preventDefault();
        this.uploadArea.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            this.handleFile(files[0]);
        }
    }

    handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.handleFile(file);
        }
    }

    handleFile(file) {
        // Validate file type
        if (file.type !== 'application/pdf') {
            this.showAlert('Please select a PDF file.', 'error');
            return;
        }

        // Validate file size (10MB limit)
        const maxSize = 10 * 1024 * 1024; // 10MB in bytes
        if (file.size > maxSize) {
            this.showAlert('File size must be less than 10MB.', 'error');
            return;
        }

        this.selectedFile = file;
        this.displayFileInfo(file);
        this.convertBtn.disabled = false;
        this.hideAlert();
    }

    displayFileInfo(file) {
        this.fileName.textContent = file.name;
        this.fileSize.textContent = this.formatFileSize(file.size);
        this.fileInfo.classList.add('show');
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    async convertFile() {
        if (!this.selectedFile) {
            this.showAlert('Please select a PDF file first.', 'error');
            return;
        }

        this.convertBtn.disabled = true;
        this.showProgress();
        this.hideAlert();

        const formData = new FormData();
        formData.append('file', this.selectedFile);
        formData.append('language', this.languageSelect.value);

        try {
            // Simulate progress
            this.updateProgress(20, 'Uploading file...');
            
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            this.updateProgress(60, 'Extracting text from PDF...');
            
            const result = await response.json();

            if (response.ok && result.success) {
                this.updateProgress(100, 'Conversion completed!');
                setTimeout(() => {
                    this.showResult(result);
                }, 1000);
            } else {
                throw new Error(result.error || 'Conversion failed');
            }
        } catch (error) {
            this.hideProgress();
            this.showAlert(error.message, 'error');
            this.convertBtn.disabled = false;
        }
    }

    showProgress() {
        this.progressContainer.classList.add('show');
        this.resultContainer.classList.remove('show');
    }

    hideProgress() {
        this.progressContainer.classList.remove('show');
    }

    updateProgress(percentage, text) {
        this.progressFill.style.width = percentage + '%';
        this.progressText.textContent = text;
    }

    showResult(result) {
        this.hideProgress();
        this.resultContainer.classList.add('show');
        
        const textLength = result.text_length || 0;
        const estimatedDuration = Math.ceil(textLength / 150); // Rough estimate: 150 words per minute
        
        this.resultText.innerHTML = `
            <strong>Conversion successful!</strong><br>
            Text extracted: ${textLength.toLocaleString()} characters<br>
            Estimated audio duration: ~${estimatedDuration} minutes
        `;
        
        this.downloadBtn.href = `/api/download/${result.filename}`;
        this.downloadBtn.download = result.filename;
    }

    showAlert(message, type) {
        this.alertBox.textContent = message;
        this.alertBox.className = `alert ${type} show`;
    }

    hideAlert() {
        this.alertBox.classList.remove('show');
    }

    reset() {
        this.selectedFile = null;
        this.fileInput.value = '';
        this.fileInfo.classList.remove('show');
        this.resultContainer.classList.remove('show');
        this.progressContainer.classList.remove('show');
        this.convertBtn.disabled = true;
        this.hideAlert();
        
        // Reset upload area
        this.uploadArea.classList.remove('dragover');
    }
}

// Initialize the converter when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new PDFConverter();
});

// Add some nice animations
document.addEventListener('DOMContentLoaded', () => {
    // Animate features on scroll
    const features = document.querySelectorAll('.feature');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                setTimeout(() => {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }, index * 100);
            }
        });
    });

    features.forEach(feature => {
        feature.style.opacity = '0';
        feature.style.transform = 'translateY(20px)';
        feature.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(feature);
    });
});

