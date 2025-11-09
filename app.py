# ============================================================
# IMPORTS AND DEPENDENCIES
# ============================================================
# Flask imports for web server functionality
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
import os

# Utility imports for processing and error handling
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

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")

# Load Gemini API key from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini API when available
if genai and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

print(f"genai loaded: {genai is not None}")
print(f"GEMINI_API_KEY present: {bool(GEMINI_API_KEY)}")

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
    personality_parts = []


    for char in selected_characteristics:
        intensity_value = characteristic_intensities.get(char, 1.0)
        personality_parts.append(f"{intensity_labels.get(intensity_value, 'moderately')} {char}")

    if len(personality_parts) > 1:
        personality = ", ".join(personality_parts[:-1]) + f", and {personality_parts[-1]}"
    else:
        personality = personality_parts[0]

    # Build demographic context parts (age, gender, location)
    context_parts = []
    generated_age = None

    if age_min and age_max:
        generated_age = random.randint(age_min, age_max)
        context_parts.append(f"age {generated_age}")
    elif age_min:
        generated_age = age_min
        context_parts.append(f"age {age_min}+")
    elif age_max:
        generated_age = age_max
        context_parts.append(f"age up to {age_max}")
    if gender:
        context_parts.append(f"gender {gender}")
    if location:
        context_parts.append(f"from {location}")

    reviewer_context = f"a potential customer who is {personality}"
    if context_parts:
        reviewer_context += f", {', '.join(context_parts)}"

    # Build the prompt with optional document context
    document_context = ""
    if document_text and document_text.strip():
        # Truncate document text if too long (keep first 3000 chars to avoid token limits)
        truncated_doc = document_text[:3000] + "..." if len(document_text) > 3000 else document_text
        document_context = f"""

Additional context from attached document:
{truncated_doc}
"""

    gemini_prompt = f"""
You are a potential customer responding to a product idea.
The product concept is: {prompt}
{document_context}
You are {reviewer_context}.

Provide 2-4 sentences of authentic feedback. Afterwards, on a new line,
add a rating between 1 and 10 formatted exactly as: RATING: X
"""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(gemini_prompt)
        full_text = (response.text or "").strip()

        rating_match = re.search(r"RATING:\s*(\d+)", full_text, re.IGNORECASE)

        rating = int(rating_match.group(1)) if rating_match else 5
        rating = max(1, min(10, rating))
        review_text = re.sub(r"\s*RATING:\s*\d+\s*$", "", full_text, flags=re.IGNORECASE).strip()
        if not review_text:
            review_text = "No feedback received."

        # Generate random name for persona
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        if generated_age:
            persona_name = f"{first_name} {last_name}, {generated_age}"
        else:
            persona_name = f"{first_name} {last_name}"

        # Package review with metadata about the persona
        metadata = {
            "persona_name": persona_name,
            "persona_descriptor": reviewer_context,
            "characteristics": selected_characteristics,
            "characteristic_intensities": characteristic_intensities,
            "sentiment_rating": rating,
            "personality_description": personality,
            "age_range": f"{age_min}-{age_max}" if age_min and age_max else None,
            "age": generated_age,
            "gender": gender or None,
            "location": location or None,
        }

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
        if review_text:
            review_id = review.get("id", len(formatted_feedbacks) + 1)
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
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
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
            age_min = request.form.get("ageMin")
            age_max = request.form.get("ageMax")
            gender = request.form.get("gender")
            location = request.form.get("location")
            
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
            age_min = data.get("ageMin")
            age_max = data.get("ageMax")
            gender = data.get("gender")
            location = data.get("location")
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
        persona_name = f"{first_name} {last_name}"

        # Vary ratings slightly (6-8 out of 10)
        rating = 6 + (idx % 3)

        # Build fallback review with generic but helpful feedback
        reviews.append(
            {
                "id": idx + 1,
                "index": idx + 1,
                "review": (
                    f"As a {template['persona_descriptor'].lower()}, I've considered \"{snippet}\". "
                    "It shows promise, but clarifying the value proposition and next validation steps would help."
                ),
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