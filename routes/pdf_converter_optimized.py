from flask import Blueprint, request, jsonify, send_from_directory, current_app
import os
import fitz  # PyMuPDF
from gtts import gTTS
from werkzeug.utils import secure_filename
import uuid
import tempfile
import threading
import time

pdf_converter_bp = Blueprint('pdf_converter', __name__)

# Configure upload and output folders
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'

def ensure_folders():
    """Ensure upload and output folders exist"""
    upload_path = os.path.join(current_app.root_path, UPLOAD_FOLDER)
    output_path = os.path.join(current_app.root_path, OUTPUT_FOLDER)
    os.makedirs(upload_path, exist_ok=True)
    os.makedirs(output_path, exist_ok=True)
    return upload_path, output_path

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'

def pdf_to_text(pdf_path):
    """Extract text from PDF file"""
    text = ""
    try:
        print(f"DEBUG: Opening PDF file: {pdf_path}")
        with fitz.open(pdf_path) as doc:
            print(f"DEBUG: PDF opened successfully, {doc.page_count} pages")
            for page_num, page in enumerate(doc):
                print(f"DEBUG: Processing page {page_num + 1}")
                page_text = page.get_text()
                text += page_text
                print(f"DEBUG: Page {page_num + 1} text length: {len(page_text)}")
        print(f"DEBUG: Total text extracted: {len(text)} characters")
    except Exception as e:
        print(f"DEBUG: Error in pdf_to_text: {str(e)}")
        raise Exception(f"Error reading PDF: {str(e)}")
    return text

def create_tts_with_retry(text, language='en', max_retries=3):
    """Create gTTS object with retry mechanism"""
    for attempt in range(max_retries):
        try:
            print(f"DEBUG: Creating gTTS object (attempt {attempt + 1}/{max_retries})")
            tts = gTTS(text=text, lang=language, slow=False)
            print(f"DEBUG: gTTS object created successfully on attempt {attempt + 1}")
            return tts
        except Exception as e:
            print(f"DEBUG: gTTS creation failed on attempt {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # Exponential backoff
                print(f"DEBUG: Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            else:
                raise e

def save_tts_with_retry(tts, output_path, max_retries=3):
    """Save gTTS object with retry mechanism"""
    for attempt in range(max_retries):
        try:
            print(f"DEBUG: Saving gTTS to {output_path} (attempt {attempt + 1}/{max_retries})")
            tts.save(output_path)
            print(f"DEBUG: gTTS saved successfully on attempt {attempt + 1}")
            return
        except Exception as e:
            print(f"DEBUG: gTTS save failed on attempt {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # Exponential backoff
                print(f"DEBUG: Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            else:
                raise e

def text_to_mp3_optimized(text, output_path, language='en', timeout=900):
    """Convert text to MP3 using gTTS with optimized chunking and delays"""
    result = {'success': False, 'error': None}
    
    def convert():
        try:
            print(f"DEBUG: Starting optimized gTTS conversion, text length: {len(text)}, language: {language}")
            
            # Use very small chunks for maximum reliability
            max_chunk_size = 1000  # Even smaller chunks
            chunk_delay = 2  # 2 second delay between chunks
            
            if len(text) > max_chunk_size:
                print(f"DEBUG: Text is long ({len(text)} chars), chunking into {max_chunk_size} char pieces")
                chunks = [text[i:i+max_chunk_size] for i in range(0, len(text), max_chunk_size)]
                
                # Create temporary files for each chunk
                temp_files = []
                for i, chunk in enumerate(chunks):
                    print(f"DEBUG: Processing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
                    temp_file = f"{output_path}.chunk_{i}.mp3"
                    
                    # Create and save with retry
                    tts = create_tts_with_retry(chunk, language)
                    save_tts_with_retry(tts, temp_file)
                    
                    temp_files.append(temp_file)
                    print(f"DEBUG: Chunk {i+1} saved successfully")
                    
                    # Add delay between chunks to avoid rate limiting
                    if i < len(chunks) - 1:  # Don't delay after the last chunk
                        print(f"DEBUG: Waiting {chunk_delay} seconds before next chunk...")
                        time.sleep(chunk_delay)
                
                # Combine chunks (simple concatenation for now)
                print("DEBUG: Combining chunks...")
                with open(output_path, 'wb') as outfile:
                    for temp_file in temp_files:
                        with open(temp_file, 'rb') as infile:
                            outfile.write(infile.read())
                        os.remove(temp_file)  # Clean up temp file
                
                print("DEBUG: Chunks combined successfully")
            else:
                print("DEBUG: Text size is manageable, processing as single chunk")
                tts = create_tts_with_retry(text, language)
                save_tts_with_retry(tts, output_path)
                print("DEBUG: Single chunk processed successfully")
            
            result['success'] = True
        except Exception as e:
            print(f"DEBUG: Error in text_to_mp3_optimized: {str(e)}")
            result['error'] = str(e)
    
    # Run conversion in a separate thread with timeout
    thread = threading.Thread(target=convert)
    thread.daemon = True
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        print(f"DEBUG: gTTS conversion timed out after {timeout} seconds")
        raise Exception(f"Text-to-speech conversion timed out after {timeout} seconds. Please try with a smaller PDF or check your internet connection.")
    
    if not result['success']:
        raise Exception(f"Error generating MP3: {result['error']}")

@pdf_converter_bp.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and conversion"""
    print("DEBUG: Upload route called")
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            print("DEBUG: No file in request")
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        print(f"DEBUG: File received: {file.filename}")
        
        if file.filename == '':
            print("DEBUG: Empty filename")
            return jsonify({'error': 'No file selected'}), 400

        if not allowed_file(file.filename):
            print("DEBUG: File type not allowed")
            return jsonify({'error': 'Only PDF files are allowed'}), 400

        # Check file size (10MB limit)
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        print(f"DEBUG: File size: {file_size} bytes")
        
        max_size = 10 * 1024 * 1024  # 10MB
        if file_size > max_size:
            print("DEBUG: File too large")
            return jsonify({'error': 'File size must be less than 10MB'}), 400

        # Ensure folders exist
        upload_path, output_path = ensure_folders()
        print(f"DEBUG: Upload path: {upload_path}, Output path: {output_path}")

        # Generate unique filename
        unique_id = str(uuid.uuid4())
        pdf_filename = f"{unique_id}_{secure_filename(file.filename)}"
        pdf_path = os.path.join(upload_path, pdf_filename)
        print(f"DEBUG: Saving file to: {pdf_path}")
        
        # Save uploaded file
        file.save(pdf_path)
        print("DEBUG: File saved successfully")

        # Validate that it's actually a PDF file
        print("DEBUG: Validating PDF file")
        try:
            with fitz.open(pdf_path) as doc:
                page_count = doc.page_count
                print(f"DEBUG: PDF has {page_count} pages")
                if page_count == 0:
                    os.remove(pdf_path)
                    return jsonify({'error': 'Invalid PDF file - no pages found'}), 400
        except Exception as e:
            print(f"DEBUG: PDF validation failed: {str(e)}")
            os.remove(pdf_path)
            return jsonify({'error': 'Invalid PDF file format'}), 400

        # Extract text from PDF
        print("DEBUG: Starting text extraction")
        text = pdf_to_text(pdf_path)
        print(f"DEBUG: Text extracted, length: {len(text)}")
        
        if not text.strip():
            # Clean up uploaded file
            os.remove(pdf_path)
            print("DEBUG: No text found in PDF")
            return jsonify({'error': 'The PDF contains no readable text. Please ensure your PDF has text content, not just images.'}), 400

        # Check text length (limit to prevent very long audio files)
        max_text_length = 30000  # Keep the 30k limit
        if len(text) > max_text_length:
            print(f"DEBUG: Text too long ({len(text)} chars), truncating to {max_text_length}")
            text = text[:max_text_length] + "... (text truncated due to length limit)"

        # Generate MP3 filename
        mp3_filename = f"{unique_id}_{os.path.splitext(secure_filename(file.filename))[0]}.mp3"
        mp3_path = os.path.join(output_path, mp3_filename)
        print(f"DEBUG: MP3 will be saved to: {mp3_path}")

        # Get language from request (default to English)
        language = request.form.get('language', 'en')
        print(f"DEBUG: Language: {language}")
        
        # Validate language code
        supported_languages = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh']
        if language not in supported_languages:
            language = 'en'

        # Convert text to MP3 with optimized approach
        print("DEBUG: Starting optimized text-to-speech conversion")
        text_to_mp3_optimized(text, mp3_path, language, timeout=900)  # 15 minute timeout
        print("DEBUG: Text-to-speech conversion completed")

        # Clean up uploaded PDF file
        os.remove(pdf_path)
        print("DEBUG: Cleaned up PDF file")

        print("DEBUG: Conversion successful, returning response")
        return jsonify({
            'success': True,
            'filename': mp3_filename,
            'text_length': len(text),
            'message': 'Conversion completed successfully'
        })

    except Exception as e:
        print(f"DEBUG: Exception occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Clean up any files if they exist
        try:
            if 'pdf_path' in locals() and os.path.exists(pdf_path):
                os.remove(pdf_path)
            if 'mp3_path' in locals() and os.path.exists(mp3_path):
                os.remove(mp3_path)
        except:
            pass
        
        return jsonify({'error': f'An error occurred during conversion: {str(e)}'}), 500

@pdf_converter_bp.route('/download/<filename>')
def download_file(filename):
    """Download converted MP3 file"""
    try:
        _, output_path = ensure_folders()
        return send_from_directory(
            output_path,
            filename,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': 'File not found'}), 404

@pdf_converter_bp.route('/status')
def status():
    """API status endpoint"""
    return jsonify({
        'status': 'online',
        'service': 'PDF to MP3 Converter'
    })

