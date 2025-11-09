# ============================================================
# IMPORTS AND DEPENDENCIES
# ============================================================
# Flask imports for web server functionality
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
import os

# Utility imports for processing and error handling
import json
import math
import random
import re
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from werkzeug.utils import secure_filename

try:
    import google.generativeai as genai  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    genai = None  # type: ignore[assignment]

try:
    import pdfplumber  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    pdfplumber = None  # type: ignore[assignment]

try:
    from docx import Document  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    Document = None  # type: ignore[assignment]

try:
    from elevenlabs.client import ElevenLabs  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    ElevenLabs = None  # type: ignore[assignment]

try:
    from openai import OpenAI  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore[assignment]

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")

# Load API keys from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configure Gemini API when available
if genai and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Configure ElevenLabs client
elevenlabs_client = ElevenLabs(api_key=ELEVEN_API_KEY) if (ELEVEN_API_KEY and ElevenLabs) else None

# Configure OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY) if (OPENAI_API_KEY and OpenAI) else None

# Voice configuration for ElevenLabs
VOICE_DEFAULT = (
    os.getenv("ELEVENLABS_VOICE_ID_DEFAULT")
    or os.getenv("ELEVENLABS_VOICE_ID")
    or os.getenv("ELEVENLABS_VOICE_ID_NEUTRAL")
)
VOICE_MALE = os.getenv("ELEVENLABS_VOICE_ID_MALE")
VOICE_FEMALE = os.getenv("ELEVENLABS_VOICE_ID_FEMALE")
VOICE_NONBINARY = os.getenv("ELEVENLABS_VOICE_ID_NONBINARY") or os.getenv("ELEVENLABS_VOICE_ID_NEUTRAL")

CALL_HISTORY_LIMIT = 6

print(f"genai loaded: {genai is not None}")
print(f"GEMINI_API_KEY present: {bool(GEMINI_API_KEY)}")
print(f"ElevenLabs client loaded: {elevenlabs_client is not None}")
print(f"OpenAI client loaded: {openai_client is not None}")

# Intensity levels
INTENSITY_LEVELS = [0.9, 1.0, 1.1]

# Available persona traits
AVAILABLE_CHARACTERISTICS = [
    "analytical",
    "creative",
    "practical",
    "emotional",
    "skeptical",
    "optimistic",
    "detail-oriented",
    "impulsive",
    "cautious",
    "adventurous",
]

# Allowed file extensions
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}


def allowed_file(filename):
    """Check if file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_int(value):
    """Safely parse integers from form inputs."""
    try:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        value = str(value).strip()
        if not value:
            return None
        return int(value)
    except (ValueError, TypeError):
        return None


def extract_text_from_pdf(file):
    """Extract text from a PDF file."""
    if not pdfplumber:
        return None, "PDF parsing library (pdfplumber) not installed"
    try:
        # Reset file pointer to beginning
        file.seek(0)
        text_content = []
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_content.append(text)
        return "\n\n".join(text_content), None
    except Exception as exc:
        return None, f"Error parsing PDF: {str(exc)}"


def extract_text_from_docx(file):
    """Extract text from a DOCX file."""
    if not Document:
        return None, "DOCX parsing library (python-docx) not installed"
    try:
        # Reset file pointer to beginning
        file.seek(0)
        doc = Document(file)
        text_content = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_content.append(paragraph.text)
        return "\n\n".join(text_content), None
    except Exception as exc:
        return None, f"Error parsing DOCX: {str(exc)}"


def parse_uploaded_file(file):
    """Parse uploaded file and return extracted text."""
    if not file or not file.filename:
        return None, None

    if not allowed_file(file.filename):
        return None, "File type not allowed. Please upload PDF, DOC, or DOCX files."

    filename = secure_filename(file.filename)
    extension = filename.rsplit(".", 1)[1].lower()

    try:
        if extension == "pdf":
            return extract_text_from_pdf(file)
        elif extension in ["doc", "docx"]:
            return extract_text_from_docx(file)
        else:
            return None, f"Unsupported file type: {extension}"
    except Exception as exc:
        return None, f"Error processing file: {str(exc)}"

# Random name pools for persona generation
FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Quinn",
    "Sage", "River", "Phoenix", "Dakota", "Cameron", "Skyler", "Rowan", "Harper",
    "Finley", "Emerson", "Reese", "Parker", "Blake", "Kendall", "Hayden", "Peyton",
    "Drew", "Logan", "Charlie", "Jamie", "Jessie", "Micah", "Adrian", "Ash",
    "Sam", "Kai", "Ellis", "Elliot", "Aubrey", "Bailey", "Brook", "Dylan"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores"
]


# ============================================================
# ROUTE HANDLERS
# ============================================================

@app.route("/")
def index():
    """Render main page"""
    return render_template("index.html", characteristics=AVAILABLE_CHARACTERISTICS)


def generate_review(  # pylint: disable=too-many-arguments
    prompt,
    selected_characteristics,
    characteristic_intensities,
    age_min=None,
    age_max=None,
    gender=None,
    location=None,
    document_text=None,
):
    """Generate a single review using the Gemini API."""
    if not genai or not GEMINI_API_KEY:
        return None, "Gemini API key not configured"
    if not selected_characteristics:
        return None, "No characteristics selected"

    intensity_labels = {0.9: "somewhat", 1.0: "moderately", 1.1: "very"}
    trait_descriptions = []
    for char in selected_characteristics:
        intensity_value = characteristic_intensities.get(char, 1.0)
        trait_descriptions.append(f"{intensity_labels.get(intensity_value, 'moderately')} {char}")

    personality_summary = ", ".join(trait_descriptions)

    age_min_val = parse_int(age_min)
    age_max_val = parse_int(age_max)

    # Generate a specific random age for this persona
    generated_age = None
    if age_min_val is not None and age_max_val is not None:
        if age_min_val > age_max_val:
            age_min_val, age_max_val = age_max_val, age_min_val
        generated_age = random.randint(age_min_val, age_max_val)
    elif age_min_val is not None:
        generated_age = random.randint(age_min_val, 100)
    elif age_max_val is not None:
        generated_age = random.randint(18, age_max_val)
    else:
        generated_age = random.randint(22, 65)

    persona_constraints = []
    if generated_age:
        persona_constraints.append(f"Age: exactly {generated_age} years old")

    if gender:
        persona_constraints.append(f"Gender: {gender}")
    if location:
        persona_constraints.append(f"Based in {location}")

    constraints_text = "\n".join(f"- {item}" for item in persona_constraints) if persona_constraints else "- No specific demographic constraints provided."
    traits_text = "\n".join(f"- {desc}" for desc in trait_descriptions)

    document_context = ""
    if document_text and document_text.strip():
        truncated_doc = document_text[:3000] + "..." if len(document_text) > 3000 else document_text
        document_context = f"""

Supporting material supplied by the user:
\"\"\"{truncated_doc}\"\"\"
"""

    instruction_schema = """
Return ONLY valid JSON (no code fences) with this structure:
{
  "persona": {
    "name": "First Last",
    "age": integer,
    "gender": "Gender or leave empty",
    "location": "City, Region or leave empty",
    "profession": "Job title",
    "tone": "One-word tone describing how they speak",
    "descriptor": "Short sentence describing the persona",
    "traits": ["list", "of", "traits"],
    "motivations": "Optional short phrase about what drives them"
  },
  "review": {
    "text": "2-4 sentences of authentic feedback grounded in the product idea and persona perspective.",
    "rating": integer between 1 and 10,
    "summary": "Optional one sentence TL;DR of the feedback"
  }
}
"""

    gemini_prompt = f"""
You are crafting a realistic customer persona and their feedback about a product IDEA/CONCEPT being pitched.

Product Concept Being Pitched:
\"\"\"{prompt}\"\"\"

Primary persona traits to embody:
{traits_text}

Persona constraints and user-supplied demographic preferences:
{constraints_text}
{document_context}

IMPORTANT: The persona is evaluating this CONCEPT/IDEA based on the description provided. They have NOT used the product (it doesn't exist yet). They should:
- Give feedback on the idea itself and its potential
- Share their thoughts on whether this would appeal to them or solve a problem they have
- Raise any concerns, questions, or suggestions about the concept
- NOT pretend they have used, seen, or experienced the product
- NOT hallucinate features or experiences beyond what's described

The review must reference specifics from the product concept description and evaluate its viability from the persona's perspective.

{instruction_schema}
Fill in missing demographic fields with plausible details that still align with the constraints and traits. Keep the JSON concise, valid, and free of additional commentary.
"""

    def build_metadata_from_text(raw_text):
        """Fallback parser when JSON output is unavailable."""
        rating_match = re.search(r"RATING:\s*(\d+)", raw_text, re.IGNORECASE)
        rating = int(rating_match.group(1)) if rating_match else 5
        rating = max(1, min(10, rating))
        review_text = re.sub(r"\s*RATING:\s*\d+\s*$", "", raw_text, flags=re.IGNORECASE).strip()
        if not review_text:
            review_text = "No feedback received."

        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        persona_name = f"{first_name} {last_name}"

        # Add age to name if available
        if generated_age:
            persona_name = f"{persona_name}, {generated_age}"

        descriptor = f"{personality_summary} customer persona".strip().capitalize()

        # Package review with metadata about the persona
        metadata = {
            "persona_name": persona_name,
            "persona_descriptor": descriptor,
            "characteristics": selected_characteristics,
            "characteristic_intensities": characteristic_intensities,
            "sentiment_rating": rating,
            "personality_description": descriptor,
            "age_range": f"{age_min_val}-{age_max_val}" if age_min_val is not None and age_max_val is not None else None,
            "age": generated_age,
            "gender": gender or None,
            "location": location or None,
            "tone": None,
            "profession": None,
            "traits_summary": personality_summary,
            "source_documents_used": bool(document_text and document_text.strip()),
        }
        return review_text, metadata

    try:
        model = genai.GenerativeModel("gemini-2.0-flash-lite")
        response = model.generate_content(gemini_prompt)
        raw_output = (response.text or "").strip()

        cleaned_output = raw_output
        if cleaned_output.startswith("```"):
            cleaned_output = re.sub(r"^```(?:json)?", "", cleaned_output, flags=re.IGNORECASE).strip()
            cleaned_output = re.sub(r"```$", "", cleaned_output).strip()

        parsed = None
        if cleaned_output:
            try:
                parsed = json.loads(cleaned_output)
            except json.JSONDecodeError:
                print("⚠️ Gemini returned non-JSON response; falling back to text parser.")

        if not parsed or not isinstance(parsed, dict):
            review_text, metadata = build_metadata_from_text(raw_output)
            return {"text": review_text, "metadata": metadata}, None

        persona_info = parsed.get("persona", {}) or {}
        review_info = parsed.get("review", {}) or {}

        review_text = (review_info.get("text") or "").strip()
        if not review_text:
            review_text, metadata = build_metadata_from_text(raw_output)
            return {"text": review_text, "metadata": metadata}, None

        rating_value = parse_int(review_info.get("rating"))
        if rating_value is None:
            rating_value = 5
        rating_value = max(1, min(10, rating_value))

        persona_name = (persona_info.get("name") or "").strip()
        if not persona_name:
            persona_name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

        # Use our pre-generated random age for consistency, fallback to Gemini's age if not available
        persona_age = generated_age if generated_age else parse_int(persona_info.get("age"))

        # Add age to persona name if available
        if persona_age:
            persona_name = f"{persona_name}, {persona_age}"

        persona_gender = (persona_info.get("gender") or gender or "").strip() or None
        persona_location = (persona_info.get("location") or location or "").strip() or None
        persona_profession = (persona_info.get("profession") or "").strip() or None
        persona_tone = (persona_info.get("tone") or "").strip() or None
        persona_descriptor = (persona_info.get("descriptor") or persona_info.get("summary") or "").strip()
        if not persona_descriptor:
            persona_descriptor = f"{personality_summary} customer persona".capitalize()

        persona_traits = persona_info.get("traits")
        if not isinstance(persona_traits, list) or not persona_traits:
            persona_traits = selected_characteristics

        metadata = {
            "persona_name": persona_name,
            "persona_descriptor": persona_descriptor,
            "characteristics": persona_traits,
            "characteristic_intensities": characteristic_intensities,
            "sentiment_rating": rating_value,
            "personality_description": persona_descriptor,
            "age_range": f"{age_min_val}-{age_max_val}" if age_min_val is not None and age_max_val is not None else None,
            "age": persona_age,
            "gender": persona_gender,
            "location": persona_location,
            "profession": persona_profession,
            "tone": persona_tone,
            "motivations": persona_info.get("motivations"),
            "traits_summary": personality_summary,
            "source_documents_used": bool(document_text and document_text.strip()),
        }
        review_summary = (review_info.get("summary") or "").strip()
        if review_summary:
            metadata["review_summary"] = review_summary

        return {"text": review_text, "metadata": metadata}, None
    except Exception as exc:  # pragma: no cover - network failure
        print("🔥 Error generating review:", exc)
        traceback.print_exc()
        return None, f"Gemini error: {exc}"


def generate_feedback_summary(reviews):
    """Generate Glows and Grows summary from all persona feedbacks using Gemini API."""
    print(f"🔍 [generate_feedback_summary] Called with {len(reviews)} reviews")
    print(f"🔍 [generate_feedback_summary] genai available: {genai is not None}")
    print(f"🔍 [generate_feedback_summary] GEMINI_API_KEY available: {GEMINI_API_KEY is not None}")
    
    if not genai or not GEMINI_API_KEY:
        print("🔍 [generate_feedback_summary] Early return: genai or API key missing")
        return [], []
    if not reviews or len(reviews) == 0:
        print("🔍 [generate_feedback_summary] Early return: no reviews")
        return [], []
    
    print(f"🔍 [generate_feedback_summary] Proceeding with summary generation...")

    # Format reviews as "1: feedback text, 2: feedback text" etc.
    formatted_feedbacks = []
    for review in reviews:
        review_text = review.get("review", "").strip()
        if not review_text:
            continue

        review_id = review.get("id", len(formatted_feedbacks) + 1)
        metadata = review.get("metadata", {}) or {}
        persona_name = metadata.get("persona_name")
        profession = metadata.get("profession")
        tone = metadata.get("tone")
        location = metadata.get("location")
        traits = metadata.get("characteristics") or []

        persona_context_parts = []
        if persona_name:
            persona_context_parts.append(persona_name)
        if profession:
            persona_context_parts.append(profession)
        if tone:
            persona_context_parts.append(f"tone: {tone}")
        if location:
            persona_context_parts.append(location)
        if traits:
            persona_context_parts.append("traits: " + ", ".join(traits[:5]))

        persona_context = " | ".join(persona_context_parts)
        if persona_context:
            formatted_feedbacks.append(f"{review_id}: ({persona_context}) {review_text}")
        else:
            formatted_feedbacks.append(f"{review_id}: {review_text}")

    if not formatted_feedbacks:
        return [], []

    feedback_text = ", ".join(formatted_feedbacks)

    # Truncate if too long (keep first 8000 chars to avoid token limits)
    if len(feedback_text) > 8000:
        feedback_text = feedback_text[:8000] + "..."

    gemini_prompt = f"""
You are analyzing multiple customer feedback responses about a product idea. Below are the numbered feedbacks:

{feedback_text}

Analyze all these feedbacks and summarize them into two categories:

1. **Glows**: What aspects of the product idea are generally positive, well-received, or show promise? List 3-5 key strengths.

2. **Grows**: What areas need improvement, what concerns were raised, or what aspects were criticized? List 3-5 key areas for improvement.

Format your response EXACTLY as follows (use these exact section headers):

GLOWS:
- [First positive point]
- [Second positive point]
- [Third positive point]
- [Fourth positive point]
- [Fifth positive point if applicable]

GROWS:
- [First area for improvement]
- [Second area for improvement]
- [Third area for improvement]
- [Fourth area for improvement]
- [Fifth area for improvement if applicable]

Keep each point concise (one sentence or short phrase). Focus on the most common themes across all feedbacks.
"""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash-lite")
        response = model.generate_content(gemini_prompt)
        summary_text = (response.text or "").strip()

        # Parse the response to extract Glows and Grows
        glows = []
        grows = []

        # Split by sections
        glows_section = re.search(r"GLOWS:\s*(.*?)(?=GROWS:|$)", summary_text, re.IGNORECASE | re.DOTALL)
        grows_section = re.search(r"GROWS:\s*(.*?)$", summary_text, re.IGNORECASE | re.DOTALL)

        if glows_section:
            glows_text = glows_section.group(1).strip()
            # Extract bullet points (lines starting with - or •)
            glows = [
                line.strip().lstrip("-•").strip()
                for line in glows_text.split("\n")
                if line.strip() and (line.strip().startswith("-") or line.strip().startswith("•"))
            ]

        if grows_section:
            grows_text = grows_section.group(1).strip()
            # Extract bullet points (lines starting with - or •)
            grows = [
                line.strip().lstrip("-•").strip()
                for line in grows_text.split("\n")
                if line.strip() and (line.strip().startswith("-") or line.strip().startswith("•"))
            ]

        # Fallback: if parsing failed, try to extract any list items
        if not glows and not grows:
            # Try alternative parsing
            lines = summary_text.split("\n")
            current_section = None
            for line in lines:
                line_lower = line.lower().strip()
                if "glow" in line_lower and ":" in line:
                    current_section = "glows"
                elif "grow" in line_lower and ":" in line:
                    current_section = "grows"
                elif line.strip().startswith("-") or line.strip().startswith("•"):
                    item = line.strip().lstrip("-•").strip()
                    if item and current_section:
                        if current_section == "glows":
                            glows.append(item)
                        elif current_section == "grows":
                            grows.append(item)

        # Ensure we have at least some content
        if not glows:
            glows = ["Positive aspects identified in feedback", "Strong value proposition"]
        if not grows:
            grows = ["Areas for improvement identified", "Consider refining the approach"]

        print(f"✅ Generated summary: {len(glows)} glows, {len(grows)} grows")
        return glows[:5], grows[:5]  # Limit to 5 items each

    except Exception as exc:
        print(f"🔥 Error generating feedback summary: {exc}")
        traceback.print_exc()
        # Return fallback data
        return (
            ["Strong value proposition", "Innovative approach", "Clear target audience"],
            ["Consider refining user experience", "Clarify monetization strategy", "Address technical challenges"],
        )


@app.route("/generate", methods=["POST"])
def generate():
    """
    Main API endpoint to generate multiple persona-based product reviews.

    Accepts product idea and persona parameters, uses ThreadPoolExecutor to
    generate multiple AI reviews concurrently, and stores results in session.
    """
    try:
        # Check if request contains files (multipart/form-data) or JSON
        if request.files:
            # Handle multipart/form-data with file upload
            text = (request.form.get("text") or "").strip()
            num_reviews = max(1, min(20, int(request.form.get("numReviews", 5))))
            selected_characteristics = request.form.getlist("characteristics") or []
            age_min = parse_int(request.form.get("ageMin"))
            age_max = parse_int(request.form.get("ageMax"))
            gender = (request.form.get("gender") or "").strip() or None
            location = (request.form.get("location") or "").strip() or None
            
            # Parse uploaded file if present
            document_text = None
            if "ideaFile" in request.files:
                file = request.files["ideaFile"]
                if file and file.filename:
                    parsed_text, error = parse_uploaded_file(file)
                    if error:
                        print(f"⚠️ File parsing error: {error}")
                    elif parsed_text:
                        document_text = parsed_text
                        print(f"✅ Successfully extracted {len(parsed_text)} characters from document")
        else:
            # Handle JSON request (backward compatibility)
            data = request.get_json(silent=True) or {}
            print("Received data from frontend:", data)

            text = (data.get("text") or "").strip()
            num_reviews = max(1, min(20, int(data.get("numReviews", 5))))
            selected_characteristics = data.get("characteristics", [])
            age_min = parse_int(data.get("ageMin"))
            age_max = parse_int(data.get("ageMax"))
            gender = (data.get("gender") or "").strip() or None
            location = (data.get("location") or "").strip() or None
            document_text = None

        # Validate required inputs
        if not text:
            return jsonify({"error": "Please enter a product idea!"}), 400
        if not selected_characteristics:
            return jsonify({"error": "Please select at least one persona trait!"}), 400
        
        if not genai or not GEMINI_API_KEY:
            fallback, message = build_fallback_personas(text, num_reviews, selected_characteristics)
            session["personas"] = fallback
            session.modified = True
            return (
                jsonify(
                    {
                        "error": "Gemini API key missing",
                        "fallback": fallback,
                        "message": message,
                        "glows": [],
                        "grows": [],
                    }
                ),
                500,
            )
        # Build task list for parallel processing
        # Each task gets different intensity combinations for variety
        tasks = []
        for i in range(num_reviews):
            intensities = {
                char: INTENSITY_LEVELS[(i + j) % len(INTENSITY_LEVELS)]
                for j, char in enumerate(selected_characteristics)
            }
            tasks.append(
                {
                    "id": i + 1,
                    "prompt": text,
                    "traits": selected_characteristics,
                    "intensities": intensities,
                    "age_min": age_min,
                    "age_max": age_max,
                    "gender": gender,
                    "location": location,
                    "document_text": document_text,
                }
            )

        reviews, errors = [], []

        # Use ThreadPoolExecutor to generate reviews concurrently (max 10 parallel)
        with ThreadPoolExecutor(max_workers=min(10, num_reviews)) as executor:
            # Submit all review generation tasks
            futures = {
                executor.submit(
                    generate_review,
                    t["prompt"],
                    t["traits"],
                    t["intensities"],
                    t["age_min"],
                    t["age_max"],
                    t["gender"],
                    t["location"],
                    t.get("document_text"),
                ): t
                for t in tasks
            }

            # Collect results as they complete
            for future in as_completed(futures):
                task_info = futures[future]
                try:
                    review, err = future.result()
                    if review:
                        persona_name = review["metadata"].get("persona_name")
                        if not persona_name:
                            review["metadata"]["persona_name"] = f"Persona {task_info['id']}"
                        reviews.append(
                            {
                                "id": task_info["id"],
                                "index": task_info["id"],
                                "review": review["text"],
                                "metadata": review["metadata"],
                            }
                        )
                    elif err:
                        errors.append(f"Persona {task_info['id']}: {err}")
                except Exception as exc:  # pragma: no cover
                    errors.append(f"Persona {task_info['id']}: {exc}")
        
        # Sort reviews by ID for consistent ordering
        reviews.sort(key=lambda item: item["id"])

        # If no reviews were generated successfully, return fallback
        if not reviews:
            fallback, message = build_fallback_personas(text, num_reviews, selected_characteristics)
            session["personas"] = fallback
            session.modified = True
            print(f"🔍 [generate] No reviews generated, using fallback personas")
            return (
                jsonify(
                    {
                        "error": "No responses generated",
                        "fallback": fallback,
                        "message": message,
                        "details": errors,
                        "glows": [],
                        "grows": [],
                    }
                ),
                500,
            )
        
        # Store generated personas in session for chat feature
        session["personas"] = reviews
        session.modified = True

        # Generate summary (Glows and Grows) from all reviews
        print(f"🔍 About to call generate_feedback_summary with {len(reviews)} reviews")
        print(f"🔍 Reviews data: {[r.get('id') for r in reviews]}")
        glows, grows = generate_feedback_summary(reviews)
        print(f"🔍 Summary generated: {len(glows)} glows, {len(grows)} grows")

        # Build successful response with all generated reviews
        result = {
            "inputText": text,
            "numReviews": num_reviews,
            "reviews": reviews,
            "successCount": len(reviews),
            "errorCount": len(errors),
            "errors": errors or None,
            "glows": glows,
            "grows": grows,
        }

        print(f"✅ Successfully generated {len(reviews)} reviews with summary.")
        return jsonify(result)

    except Exception as exc:  # pragma: no cover - unexpected failure
        # Handle catastrophic errors gracefully with fallback personas
        print("🔥 Fatal error in /generate route:", exc)
        traceback.print_exc()
        text = (data.get("text") or "") if "data" in locals() else ""
        num_reviews = (int(data.get("numReviews", 5)) if "data" in locals() else 3) or 3
        characteristics = data.get("characteristics", []) if "data" in locals() else []
        fallback, message = build_fallback_personas(text, num_reviews, characteristics)
        session["personas"] = fallback
        session.modified = True
        return (
            jsonify(
                {
                    "error": str(exc),
                    "fallback": fallback,
                    "message": message,
                    "glows": [],
                    "grows": [],
                }
            ),
            500,
        )


@app.route("/chat/<int:persona_id>")
def chat(persona_id):
    """
    Render the chat interface for a specific persona.

    Loads persona data from session and displays their initial review
    along with metadata to enable conversational follow-up.
    """
    personas = session.get("personas", [])
    persona = next((p for p in personas if p.get("id") == persona_id), None)

    if not persona:
        return render_template(
            "chat.html",
            persona_id=persona_id,
            persona_name="Unknown Persona",
            descriptor="No persona details available.",
            review_text="No review data available.",
            characteristics=[],
            sentiment_rating=None,
        )
    
    # Extract persona metadata for display
    metadata = persona.get("metadata", {})
    persona_name = metadata.get("persona_name") or f"Persona {persona_id}"
    descriptor = metadata.get("persona_descriptor") or metadata.get("personality_description") or "Customer Persona"
    traits = metadata.get("characteristics", [])
    review_text = persona.get("review", "No review available.")
    sentiment_rating = metadata.get("sentiment_rating")

    # Render chat interface with persona context
    return render_template(
        "chat.html",
        persona_id=persona_id,
        persona_name=persona_name,
        descriptor=descriptor,
        review_text=review_text,
        characteristics=traits,
        sentiment_rating=sentiment_rating,
    )


@app.route("/api/chat/<int:persona_id>", methods=["POST"])
def persona_reply(persona_id):
    """
    API endpoint to generate conversational replies from a specific persona.

    Maintains persona consistency by referencing their original review
    and personality traits when responding to user questions.
    """
    # Parse user's message from request
    payload = request.get_json(silent=True) or {}
    user_msg = (payload.get("message") or "").strip()
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400
    
    # Retrieve the specific persona from session
    personas = session.get("personas", [])
    persona = next((p for p in personas if p.get("id") == persona_id), None)
    if not persona:
        return jsonify({"error": "Persona not found in session"}), 404

    # Extract persona context for maintaining consistent tone
    metadata = persona.get("metadata", {})
    tone_description = metadata.get("persona_descriptor") or metadata.get("personality_description") or "an insightful customer persona"
    review_summary = persona.get("review", "")

    # Return offline message if API is unavailable
    if not genai or not GEMINI_API_KEY:
        return jsonify(
            {
                "reply": (
                    "I'm currently offline, but I'd still encourage you to refine the idea "
                    "based on the earlier feedback we discussed."
                )
            }
        )

    chat_prompt = f"""
Continue a conversation as {tone_description}.
Earlier you provided this feedback:
"{review_summary}"

Respond to the user's latest message in a conversational, authentic tone that reflects this persona.
Avoid generic chatbot language and keep the answer concise and opinionated when appropriate.

User: {user_msg}
"""

    try:
        # Generate persona-consistent response using Gemini
        model = genai.GenerativeModel("gemini-2.0-flash-lite")
        response = model.generate_content(chat_prompt)
        reply = (response.text or "").strip()
        if not reply:
            reply = "I'm reflecting on that — could you clarify a bit more?"
        return jsonify({"reply": reply})
    except Exception as exc:  # pragma: no cover
        print("🔥 Gemini chat error:", exc)
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


# ============================================================
# VOICE CALL FUNCTIONALITY (ELEVENLABS)
# ============================================================

def _resolve_voice_id(gender_hint):
    """Resolve which ElevenLabs voice ID to use based on gender."""
    gender = (gender_hint or "").strip().lower()
    if gender in {"male", "man"} and VOICE_MALE:
        return VOICE_MALE
    if gender in {"female", "woman"} and VOICE_FEMALE:
        return VOICE_FEMALE
    if gender in {"non-binary", "nonbinary", "non binary", "nb"} and VOICE_NONBINARY:
        return VOICE_NONBINARY
    return VOICE_DEFAULT or VOICE_MALE or VOICE_FEMALE or VOICE_NONBINARY


def _build_system_prompt(persona_name, persona_descriptor, review_summary, persona_tone):
    """Build the system prompt for voice call conversation."""
    descriptor_line = persona_descriptor or persona_tone or "insightful customer persona"
    review_snippet = review_summary.strip() or "No previous review context provided."
    return (
        f"You are {persona_name}, an {descriptor_line}. "
        f"Stay in character, respond conversationally, and keep answers concise but opinionated. "
        f"Reference this earlier feedback when useful:\n\"{review_snippet}\""
    )


def _format_history(history):
    """Format conversation history for the prompt."""
    lines = []
    for turn in history[-CALL_HISTORY_LIMIT:]:
        role = turn.get("role", "")
        content = turn.get("content", "")
        if not content:
            continue
        if role == "assistant":
            lines.append(f"Persona: {content}")
        else:
            lines.append(f"User: {content}")
    return "\n".join(lines)


@app.route("/api/call/<int:persona_id>", methods=["POST"])
def call_persona(persona_id):
    """
    Handle voice call with a persona using ElevenLabs text-to-speech.

    Accepts user speech input, generates AI response, converts to speech,
    and returns both text and audio (base64 encoded).
    """
    try:
        if elevenlabs_client is None:
            return jsonify({"error": "ElevenLabs client unavailable. Set ELEVENLABS_API_KEY."}), 503

        payload = request.get_json(force=True)
        initial_greeting = bool(payload.get("initial"))
        user_text = (payload.get("message") or "").strip()

        persona_name = payload.get("persona_name")
        persona_tone = payload.get("tone") or "friendly and natural"
        persona_gender = payload.get("gender")

        personas = session.get("personas", [])
        persona = next((p for p in personas if p.get("id") == persona_id), None)
        metadata = persona.get("metadata", {}) if persona else {}

        persona_name = persona_name or metadata.get("persona_name") or f"Persona {persona_id}"
        persona_descriptor = metadata.get("persona_descriptor") or metadata.get("personality_description", "")
        review_summary = persona.get("review", "") if persona else ""

        history_key = f"call_history_{persona_id}"
        history = session.get(history_key, [])
        if isinstance(payload.get("history"), list):
            history = payload["history"][-CALL_HISTORY_LIMIT:]

        system_prompt = _build_system_prompt(persona_name, persona_descriptor, review_summary, persona_tone)
        conversation_transcript = _format_history(history)

        prompt = (
            f"{system_prompt}\n\n"
            f"Conversation so far:\n{conversation_transcript}\n\n"
            f"User: {user_text or 'Start conversation'}\n"
            f"{persona_name}:"
        )

        reply_text = ""

        # Try Gemini first
        if genai and GEMINI_API_KEY:
            try:
                model = genai.GenerativeModel("gemini-2.0-flash-exp")
                response = model.generate_content(prompt)
                candidate = (response.text or "").strip()
                if candidate:
                    reply_text = candidate
                else:
                    raise ValueError("Empty Gemini response")
            except Exception as exc:
                print("⚠️ Gemini error:", exc)
                traceback.print_exc()

        # Fallback to OpenAI
        if (not reply_text or "offline" in reply_text.lower()) and openai_client:
            try:
                oai_resp = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_text or "Start conversation"},
                    ],
                    max_tokens=150,
                )
                reply_text = oai_resp.choices[0].message.content.strip()
            except Exception as e:
                print("🔥 OpenAI fallback failed:", e)
                reply_text = "Let's keep discussing your idea — tell me more!"

        # ElevenLabs voice output
        voice_id = _resolve_voice_id(persona_gender)
        if not voice_id:
            return jsonify({"error": "No ElevenLabs voice configured for this persona."}), 500

        # Ensure we always have something to say
        if not reply_text:
            reply_text = "Hey, let's continue — what's your product idea?"

        speech_text = (
            f"Hey, I'm {persona_name}. I gave feedback on your project earlier — how may I help you today?"
            if initial_greeting
            else reply_text
        )

        speech_prompt = f"Speak in a {persona_tone} tone: {speech_text}"

        speech_result = elevenlabs_client.text_to_speech.convert(
            voice_id=voice_id,
            text=speech_prompt,
            model_id="eleven_multilingual_v2",
        )

        audio_bytes = (
            speech_result
            if isinstance(speech_result, (bytes, bytearray))
            else b"".join(chunk for chunk in speech_result if isinstance(chunk, (bytes, bytearray)))
        )

        if not audio_bytes:
            return jsonify({"error": "Failed to generate ElevenLabs audio."}), 500

        # Update session history
        if initial_greeting:
            history.append({"role": "assistant", "content": reply_text})
        else:
            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": reply_text})
        session[history_key] = history[-CALL_HISTORY_LIMIT * 2:]
        session.modified = True

        import base64
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        return jsonify({"reply": reply_text, "audio": audio_base64})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# FALLBACK SYSTEM
# ============================================================

def build_fallback_personas(text, num_reviewers, selected_characteristics):
    """Return simulated personas when live generation is unavailable."""
    base_personas = [
        {
            "persona_name": "Avery Chen",
            "persona_descriptor": "Strategy-focused product designer",
            "tone": "supportive",
            "location": "North America",
        },
        {
            "persona_name": "Jordan Ramirez",
            "persona_descriptor": "Data-driven growth specialist",
            "tone": "analytical",
            "location": "Europe",
        },
        {
            "persona_name": "Morgan Patel",
            "persona_descriptor": "User empathy researcher",
            "tone": "empathetic",
            "location": "Asia",
        },
        {
            "persona_name": "Sam Rivera",
            "persona_descriptor": "Creative marketing strategist",
            "tone": "enthusiastic",
            "location": "South America",
        },
        {
            "persona_name": "Lena Schmidt",
            "persona_descriptor": "Detail-oriented quality assurance",
            "tone": "critical",
            "location": "Europe",
        },
    ]

    if not selected_characteristics:
        selected_characteristics = ["Balanced", "Insightful"]

    snippet = text[:60] + ("…" if len(text) > 60 else "")
    reviews = []
    # Generate fallback reviews by cycling through persona templates
    for idx in range(max(1, num_reviewers)):
        # Cycle through available templates
        template = base_personas[idx % len(base_personas)]

        # Generate random name for fallback persona
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        # Generate random age between 22 and 65
        persona_age = random.randint(22, 65)
        persona_name = f"{first_name} {last_name}, {persona_age}"

        # Vary ratings slightly (6-8 out of 10)
        rating = 6 + (idx % 3)

        # Build fallback review with generic but helpful feedback
        review_text = (
            f"As a {template['persona_descriptor'].lower()}, I've considered \"{snippet}\". "
            "It shows promise, but clarifying the value proposition and next validation steps would help."
        )

        reviews.append(
            {
                "id": idx + 1,
                "index": idx + 1,
                "review": review_text,
                "metadata": {
                    "persona_name": persona_name,
                    "persona_descriptor": template["persona_descriptor"],
                    "characteristics": selected_characteristics,
                    "sentiment_rating": rating,
                    "location": template["location"],
                    "personality_description": template["persona_descriptor"],
                },
            }
        )

    message = "Using simulated persona insights (offline mode)."
    return reviews, message


if __name__ == "__main__":
    app.run(debug=True)