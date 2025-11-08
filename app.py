from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from dotenv import load_dotenv
import os
import re

try:
    import google.generativeai as genai  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    genai = None  # type: ignore[assignment]

from neuralseek_client import (
    NEURALSEEK_API_KEY,
    REVIEWER_PERSONAS,
    call_neuralseek_chat,
    create_dummy_reviewer,
    generate_reviewers,
)

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret')

# Load Gemini API key from environment variables
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Configure Gemini API when available
if genai and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

@app.route('/')
def home():
    """Render the main page"""
    return render_template('index.html')

@app.route('/index')
def index():
    """Alias for home route"""
    return render_template('index.html')


@app.route('/generate', methods=['GET', 'POST'])
def generate():
    """Handle form submission and generate multiple reviews using NeuralSeek API"""
    if request.method == 'GET':
        stored_reviewers = session.get('reviewers')
        if not stored_reviewers:
            return redirect(url_for('home'))

        text = session.get('product_description', '')
        return render_template('reviews.html', reviewers=stored_reviewers, text=text)

    # Support both form data and JSON
    if request.is_json:
        data = request.get_json(silent=True) or {}
        text = data.get('text', '').strip()
        num_reviews = int(data.get('numReviews', session.get('num_reviewers', 5)))
    else:
        text = request.form.get('text_input', '').strip()
        num_reviews = int(request.form.get('num_reviewers', session.get('num_reviewers', 5)))

    if not text:
        if request.is_json:
            return jsonify({'error': 'Please enter some text first!'}), 400
        return redirect(url_for('home'))

    if not NEURALSEEK_API_KEY:
        app.logger.warning("NeuralSeek API key not configured; using dummy reviewers.")

    try:
        reviewers = generate_reviewers(text, num_reviews)
    except Exception as exc:  # pragma: no cover - defensive
        app.logger.error("Error generating reviewers: %s", exc)
        limit = min(num_reviews, len(REVIEWER_PERSONAS))
        reviewers = [create_dummy_reviewer(REVIEWER_PERSONAS[i]) for i in range(limit)]

    session['product_description'] = text
    session['num_reviewers'] = num_reviews
    session['reviewers'] = reviewers
    session['feedback_items'] = []
    session.modified = True

    if request.is_json:
        result = {
            'inputText': text,
            'numReviews': num_reviews,
            'reviews': reviewers,
            'successCount': len(reviewers),
            'errorCount': 0,
            'errors': None,
        }
        return jsonify(result)

    return render_template('reviews.html', reviewers=reviewers, text=text)

@app.route('/chat/<int:reviewer_id>')
def chat(reviewer_id):
    """Render chat page for a specific reviewer"""
    # Get reviewer info from personas
    if 1 <= reviewer_id <= len(REVIEWER_PERSONAS):
        persona = REVIEWER_PERSONAS[reviewer_id - 1]
        reviewer = {
            "id": reviewer_id,
            "name": persona["name"],
            "profession": persona["profession"]
        }
    else:
        reviewer = {
            "id": reviewer_id,
            "name": "Reviewer",
            "profession": "Expert"
        }
    
    feedback_items = session.get('feedback_items', [])
    return render_template('chat.html', reviewer=reviewer, reviewer_id=reviewer_id, feedback_items=feedback_items)

@app.route('/chat/<int:reviewer_id>/message', methods=['POST'])
def chat_message(reviewer_id):
    """Handle chat messages and return AI response"""
    data = request.get_json()
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400
    
    # Get reviewer persona
    if 1 <= reviewer_id <= len(REVIEWER_PERSONAS):
        persona = REVIEWER_PERSONAS[reviewer_id - 1]
    else:
        persona = REVIEWER_PERSONAS[0]  # Default to first persona
    
    # Build conversation payload for NeuralSeek
    messages = [
        {"role": "system", "content": persona["persona"]},
        {"role": "user", "content": user_message},
    ]

    response_text = None
    if NEURALSEEK_API_KEY:
        response_text = call_neuralseek_chat(messages)

    if not response_text:
        response_text = (
            "I understand your question. Let me think about that... Based on my review, "
            "I think your idea has potential but needs refinement in certain areas."
        )
    
    return jsonify({'response': response_text})


@app.route('/summarize_feedback', methods=['POST'])
def summarize_feedback():
    if not genai:
        app.logger.error("Gemini SDK unavailable")
        return jsonify({"items": []})

    data = request.get_json(force=True) or {}
    conversation = data.get("conversation", "")

    if isinstance(conversation, list):
        conversation = "\n".join(str(item) for item in conversation)
    conversation = conversation.strip()

    if not conversation:
        return jsonify({"items": []})

    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not api_key:
        app.logger.error("Gemini API key not configured")
        return jsonify({"items": []})

    genai.configure(api_key=api_key)

    prompt = (
        "You are an assistant that extracts actionable product feedback from a chat.\n"
        "Summarize the most recent suggestions as short bullet points (3–6 words each).\n"
        "Only output plain text lines.\n\n"
        f"Conversation:\n{conversation}"
    )

    model_names = ["models/gemini-1.5-flash", "models/gemini-pro"]
    items = []
    last_error = None

    for model_name in model_names:
        try:
            model = genai.GenerativeModel(model_name=model_name)
            response = model.generate_content(prompt)
            text_output = getattr(response, "text", "") or ""

            if not text_output and getattr(response, "candidates", None):
                candidate = response.candidates[0]  # type: ignore[index]
                parts = getattr(candidate, "content", None)
                if parts and getattr(parts, "parts", None):
                    text_output = "\n".join(
                        getattr(part, "text", "") for part in parts.parts if getattr(part, "text", "")
                    )

            raw_lines = text_output.splitlines()
            items = [line.strip("-• ").strip() for line in raw_lines if line.strip()]

            if items:
                break
        except Exception as exc:  # pragma: no cover - defensive
            last_error = exc
            app.logger.error("Gemini summarization error (%s): %s", model_name, exc)

    if not items and last_error:
        app.logger.error("Gemini summarization ultimately failed: %s", last_error)

    existing_items = session.get("feedback_items", [])
    normalized_existing = {item.lower() for item in existing_items}
    for item in items:
        if item and item.lower() not in normalized_existing:
            existing_items.append(item)
            normalized_existing.add(item.lower())

    session["feedback_items"] = existing_items
    session.modified = True

    return jsonify({"items": items})


@app.route('/apply_feedback', methods=['POST'])
def apply_feedback():
    data = request.get_json(silent=True) or {}
    selected_items = data.get("selected_items", [])

    if isinstance(selected_items, str):
        selected_items = [selected_items]

    def sanitize_item(item: str) -> str:
        if not isinstance(item, str):
            return ""
        no_tags = re.sub(r"<[^>]*?>", "", item)
        return no_tags.strip()

    sanitized_items = [sanitize_item(item) for item in selected_items]
    sanitized_items = [item for item in sanitized_items if item]

    description = session.get("product_description", "")
    if not isinstance(description, str):
        description = ""

    if sanitized_items:
        updates_text = "\n\n### Updates Applied:\n" + "\n".join(f"- {item}" for item in sanitized_items)
        updated_description = description + updates_text
    else:
        updated_description = description

    session["product_description"] = updated_description

    num_reviewers = int(session.get("num_reviewers", 5))

    try:
        reviewers = generate_reviewers(updated_description, num_reviewers)
    except Exception as exc:
        print("Error regenerating reviewers:", exc)
        limit = min(num_reviewers, len(REVIEWER_PERSONAS))
        reviewers = [create_dummy_reviewer(REVIEWER_PERSONAS[i]) for i in range(limit)]

    session["reviewers"] = reviewers

    if sanitized_items:
        remaining_feedback = [
            item for item in session.get("feedback_items", [])
            if item not in sanitized_items
        ]
        session["feedback_items"] = remaining_feedback

    session.modified = True

    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(debug=True)

