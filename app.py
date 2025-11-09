from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import traceback
import pdfplumber
from docx import Document
from io import BytesIO
import subprocess
import tempfile

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Load Gemini API key from environment variables
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Configure Gemini API
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Intensity levels
INTENSITY_LEVELS = [0.9, 1.0, 1.1]

# Available persona traits
AVAILABLE_CHARACTERISTICS = [
    "analytical", "creative", "practical", "emotional", "skeptical",
    "optimistic", "detail-oriented", "impulsive", "cautious", "adventurous"
]

# Store parsed PDF text
# Key: filename, Value: extracted text string
# You can access this dictionary to get the parsed PDF text for sending to Gemini API
PARSED_PDF_TEXT = {}


@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html', characteristics=AVAILABLE_CHARACTERISTICS)


def parse_pdf(file_content):
    """
    Parse PDF file and extract text.
    
    Args:
        file_content: Bytes content of the PDF file
        
    Returns:
        str: Extracted text from the PDF
    """
    try:
        text_parts = []
        with pdfplumber.open(BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        
        extracted_text = "\n\n".join(text_parts)
        return extracted_text.strip()
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        traceback.print_exc()
        raise


def parse_docx(file_content):
    """
    Parse .docx file and extract text.
    
    Args:
        file_content: Bytes content of the .docx file
        
    Returns:
        str: Extracted text from the document
    """
    try:
        doc = Document(BytesIO(file_content))
        text_parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        
        extracted_text = "\n\n".join(text_parts)
        return extracted_text.strip()
    except Exception as e:
        print(f"Error parsing DOCX: {e}")
        traceback.print_exc()
        raise


def parse_doc(file_content, filename):
    """
    Parse .doc file and extract text using antiword (if available).
    
    Args:
        file_content: Bytes content of the .doc file
        filename: Name of the file (for error messages)
        
    Returns:
        str: Extracted text from the document
    """
    try:
        # Check if antiword is available (system dependency)
        try:
            subprocess.run(['antiword', '-v'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise Exception(
                "antiword is not installed. For .doc file support, please install antiword:\n"
                "  macOS: brew install antiword\n"
                "  Linux: sudo apt-get install antiword\n"
                "  Or convert .doc files to .docx format"
            )
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.doc') as tmp_file:
            tmp_file.write(file_content)
            tmp_path = tmp_file.name
        
        try:
            # Use antiword to extract text
            result = subprocess.run(
                ['antiword', tmp_path],
                capture_output=True,
                text=True,
                check=True
            )
            extracted_text = result.stdout.strip()
            return extracted_text
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except subprocess.CalledProcessError as e:
        print(f"Error running antiword: {e}")
        raise Exception(f"Failed to extract text from .doc file: {e.stderr.decode() if e.stderr else str(e)}")
    except Exception as e:
        print(f"Error parsing DOC: {e}")
        traceback.print_exc()
        raise


@app.route('/parse-pdf', methods=['POST'])
def parse_pdf_endpoint():
    """
    Endpoint to upload and parse a PDF, DOC, or DOCX file.
    The extracted text is stored in PARSED_PDF_TEXT dictionary.
    
    Returns:
        JSON response with success status and filename
    """
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        filename_lower = file.filename.lower()
        
        # Check file type
        if not (filename_lower.endswith('.pdf') or 
                filename_lower.endswith('.doc') or 
                filename_lower.endswith('.docx')):
            return jsonify({"error": "File must be a PDF, DOC, or DOCX"}), 400
        
        # Read file content
        file_content = file.read()
        
        # Parse based on file type
        if filename_lower.endswith('.pdf'):
            extracted_text = parse_pdf(file_content)
            file_type = "PDF"
        elif filename_lower.endswith('.docx'):
            extracted_text = parse_docx(file_content)
            file_type = "DOCX"
        elif filename_lower.endswith('.doc'):
            extracted_text = parse_doc(file_content, file.filename)
            file_type = "DOC"
        else:
            return jsonify({"error": "Unsupported file type"}), 400
        
        # Store the parsed text in the global dictionary
        # Key: filename, Value: extracted text
        PARSED_PDF_TEXT[file.filename] = extracted_text
        
        print(f"Successfully parsed {file_type}: {file.filename}")
        print(f"Extracted {len(extracted_text)} characters")
        
        return jsonify({
            "success": True,
            "filename": file.filename,
            "file_type": file_type,
            "text_length": len(extracted_text),
            "message": f"{file_type} parsed successfully. Text stored in PARSED_PDF_TEXT['{file.filename}']"
        })
        
    except Exception as e:
        print(f"Error in /parse-pdf endpoint: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Failed to parse file: {str(e)}"}), 500


def generate_review(prompt, selected_characteristics, characteristic_intensities,
                    age_min=None, age_max=None, gender=None, location=None, pdf_text=None):
    """
    Generate single review using Gemini API.
    
    Args:
        prompt: The product idea text
        selected_characteristics: List of persona characteristics
        characteristic_intensities: Dictionary of characteristic intensities
        age_min: Minimum age
        age_max: Maximum age
        gender: Gender filter
        location: Location filter
        pdf_text: Optional PDF text to include in the prompt
                  You can also access PARSED_PDF_TEXT dictionary directly:
                  e.g., pdf_text = PARSED_PDF_TEXT.get('filename.pdf', '')
    """
    if not GEMINI_API_KEY:
        return None, "Gemini API key not configured"
    if not selected_characteristics:
        return None, "No characteristics selected"
    
    # TODO: To use parsed PDF text, you can access it from PARSED_PDF_TEXT dictionary
    # Example: pdf_text = PARSED_PDF_TEXT.get('your_file.pdf', '')
    # Then include it in your prompt below

    intensity_descriptions = {0.9: "somewhat", 1.0: "moderately", 1.1: "very"}

    # Describe personality
    parts = []
    for char in selected_characteristics:
        val = characteristic_intensities.get(char, 1.0)
        parts.append(f"{intensity_descriptions.get(val, 'moderately')} {char}")
    if len(parts) > 1:
        personality = ", ".join(parts[:-1]) + f", and {parts[-1]}"
    else:
        personality = parts[0]

    # Demographic context
    context = []
    if age_min and age_max:
        context.append(f"age {age_min}-{age_max}")
    elif age_min:
        context.append(f"age {age_min}+")
    elif age_max:
        context.append(f"age up to {age_max}")
    if gender:
        context.append(f"gender {gender}")
    if location:
        context.append(f"from {location}")

    if context:
        reviewer_context = f"a potential customer who is {personality}, {', '.join(context)}"
    else:
        reviewer_context = f"a potential customer who is {personality}"
    
    pdf_text = PARSED_PDF_TEXT.get('your_file.pdf', '') if PARSED_PDF_TEXT else ''

    # Construct Gemini prompt
    gemini_prompt = f"""You are a potential customer being presented with a product idea.
The product concept is: {prompt}

{f"Additional context from attached document:\n{pdf_text}\n" if pdf_text else ""}

You are {reviewer_context}.

Please share your honest feedback (2–4 sentences) and then provide a rating 1–10 as:
RATING: X
"""

    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(gemini_prompt)
        full_text = (response.text or "").strip()

        # Extract rating
        rating_match = re.search(r'RATING:\s*(\d+)', full_text, re.IGNORECASE)
        rating = int(rating_match.group(1)) if rating_match else 5
        rating = max(1, min(10, rating))
        review_text = re.sub(r'\s*RATING:\s*\d+\s*$', '', full_text).strip() or "No feedback received."

        avg_intensity = sum(characteristic_intensities.values()) / len(characteristic_intensities)

        metadata = {
            "characteristics": selected_characteristics,
            "characteristic_intensities": characteristic_intensities,
            "avg_intensity": avg_intensity,
            "avg_intensity_label": f"{int(avg_intensity * 100)}%",
            "sentiment_rating": rating,
            "personality_description": personality,
            "age_range": f"{age_min}-{age_max}" if age_min and age_max else None,
            "gender": gender or None,
            "location": location or None
        }

        return {"text": review_text, "metadata": metadata}, None

    except Exception as e:
        print("🔥 Error generating review:", e)
        traceback.print_exc()
        return None, f"Gemini error: {e}"


@app.route('/generate', methods=['POST'])
def generate():
    """Handle frontend POST to generate multiple feedbacks"""
    try:
        data = request.get_json(force=True)
        print("\n✅ Received data from frontend:", data)

        text = (data.get("text") or "").strip()
        num_reviews = int(data.get("numReviews", 5))
        num_reviews = max(1, min(20, num_reviews))

        selected_characteristics = data.get("characteristics", [])
        age_min, age_max = data.get("ageMin"), data.get("ageMax")
        gender, location = data.get("gender"), data.get("location")
        
        # TODO: Access parsed PDF text from PARSED_PDF_TEXT dictionary
        # Example: Get the most recently uploaded PDF or a specific filename
        # pdf_text = PARSED_PDF_TEXT.get('your_file.pdf', '') if PARSED_PDF_TEXT else ''
        # You can then pass pdf_text to generate_review() or include it in the prompt

        if not text:
            return jsonify({"error": "Please enter a product idea!"}), 400
        if not selected_characteristics:
            return jsonify({"error": "Please select at least one persona trait!"}), 400
        if not GEMINI_API_KEY:
            return jsonify({"error": "Gemini API key missing"}), 500

        tasks = []
        for i in range(num_reviews):
            intensities = {
                char: INTENSITY_LEVELS[(i + j) % len(INTENSITY_LEVELS)]
                for j, char in enumerate(selected_characteristics)
            }
            tasks.append({
                "index": i,
                "prompt": text,
                "traits": selected_characteristics,
                "intensities": intensities,
                "age_min": age_min,
                "age_max": age_max,
                "gender": gender,
                "location": location
            })

        reviews, errors = [], []

        with ThreadPoolExecutor(max_workers=min(10, num_reviews)) as executor:
            futures = {
                executor.submit(
                    generate_review,
                    t["prompt"], t["traits"], t["intensities"],
                    t["age_min"], t["age_max"], t["gender"], t["location"]
                ): t for t in tasks
            }

            for f in as_completed(futures):
                t = futures[f]
                try:
                    review, err = f.result()
                    if review:
                        reviews.append({
                            "index": t["index"] + 1,
                            "review": review["text"],
                            "metadata": review["metadata"]
                        })
                    elif err:
                        errors.append(f"Persona {t['index']+1}: {err}")
                except Exception as e:
                    errors.append(f"Persona {t['index']+1}: {str(e)}")

        reviews.sort(key=lambda x: x["index"])

        if not reviews:
            return jsonify({"error": "No responses generated", "details": errors}), 500

        result = {
            "inputText": text,
            "numReviews": num_reviews,
            "reviews": reviews,
            "successCount": len(reviews),
            "errorCount": len(errors),
            "errors": errors or None
        }

        print(f"✅ Successfully generated {len(reviews)} reviews.")
        return jsonify(result)

    except Exception as e:
        print("🔥 Fatal error in /generate route:", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
