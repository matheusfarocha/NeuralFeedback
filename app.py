from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from dotenv import load_dotenv
import os
import requests
import re

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret')

# Load API keys from environment variables
NEURALSEEK_API_KEY = os.getenv('NEURALSEEK_API_KEY')

# NeuralSeek API configuration
# Base URL: https://stagingapi.neuralseek.com/v1/{instance}
# Instance: stony39
# Endpoint: /seek
NEURALSEEK_API_BASE_URL = os.getenv('NEURALSEEK_API_BASE_URL', "https://stagingapi.neuralseek.com/v1/stony39")
NEURALSEEK_API_ENDPOINT = "/seek"

@app.route('/')
def home():
    """Render the main page"""
    return render_template('index.html')

@app.route('/index')
def index():
    """Alias for home route"""
    return render_template('index.html')

def generate_review_variation(prompt, variation_index):
    """
    Generate a review variation by slightly modifying the prompt.
    This creates different perspectives for each review.
    """
    variations = [
        f"Provide a detailed review of: {prompt}",
        f"Give your honest opinion about: {prompt}",
        f"Analyze and critique: {prompt}",
        f"Evaluate from a professional perspective: {prompt}",
        f"Share your thoughts on: {prompt}",
        f"Review with focus on quality: {prompt}",
        f"Provide constructive feedback on: {prompt}",
        f"Assess the strengths and weaknesses of: {prompt}",
        f"Give a comprehensive review of: {prompt}",
        f"Analyze from a user experience perspective: {prompt}",
        f"Review with emphasis on value: {prompt}",
        f"Provide an in-depth analysis of: {prompt}",
        f"Evaluate the overall quality of: {prompt}",
        f"Share a detailed assessment of: {prompt}",
        f"Review with attention to detail: {prompt}",
        f"Provide feedback from different angles: {prompt}",
        f"Analyze the key aspects of: {prompt}",
        f"Give a balanced review of: {prompt}",
        f"Evaluate considering various factors: {prompt}",
        f"Provide a thorough review of: {prompt}"
    ]
    
    # Use variation_index to get different prompt variations
    return variations[variation_index % len(variations)]


def call_neuralseek_api(question):
    """
    Call the NeuralSeek API to get a review/answer.
    According to NeuralSeek API documentation:
    - Base URL: https://stagingapi.neuralseek.com/v1/stony39
    - Endpoint: /seek
    - Method: POST
    - Authentication: apikey header (lowercase)
    - Request Body: {"question": "string"}
    - Response: {"answer": "string", "score": number, ...}
    """
    if not NEURALSEEK_API_KEY:
        return None, "API key not configured"
    
    try:
        # NeuralSeek API uses 'apikey' header (lowercase) for authentication
        headers = {
            "accept": "application/json",
            "apikey": NEURALSEEK_API_KEY,
            "Content-Type": "application/json"
        }
        
        # Request body according to API documentation
        payload = {
            "question": question
        }
        
        # Full API URL
        api_url = f"{NEURALSEEK_API_BASE_URL}{NEURALSEEK_API_ENDPOINT}"
        
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            # Extract answer from response (according to API docs, response has 'answer' field)
            answer = data.get('answer', '')
            if not answer:
                return None, f"API response missing 'answer' field: {data}"
            return answer, None
        else:
            return None, f"API error: {response.status_code} - {response.text[:500]}"
            
    except requests.exceptions.RequestException as e:
        return None, f"Request failed: {str(e)}"
    except Exception as e:
        return None, f"Error: {str(e)}"


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
        data = request.get_json()
        text = data.get('text', '').strip()
        num_reviews = int(data.get('numReviews', session.get('num_reviewers', 5)))
    else:
        # Form-based submission (from styled frontend)
        text = request.form.get('text_input', '').strip()
        num_reviews = int(request.form.get('num_reviewers', session.get('num_reviewers', 5)))
    
    if not text:
        if request.is_json:
            return jsonify({'error': 'Please enter some text first!'}), 400
        else:
            return redirect(url_for('home'))
    
    if not NEURALSEEK_API_KEY:
        if request.is_json:
            return jsonify({'error': 'NeuralSeek API key not configured'}), 500
        else:
            return redirect(url_for('home'))
    
    from neuralseek_client import generate_reviewers, REVIEWER_PERSONAS, create_dummy_reviewer

    try:
        reviewers = generate_reviewers(text, num_reviews)
    except Exception as exc:
        print(f"Error generating reviewers: {exc}")
        limit = min(num_reviews, len(REVIEWER_PERSONAS))
        reviewers = [create_dummy_reviewer(REVIEWER_PERSONAS[i]) for i in range(limit)]

    session['product_description'] = text
    session['num_reviewers'] = num_reviews
    session['reviewers'] = reviewers
    session['feedback_items'] = []
    session.modified = True

    # If JSON request, return JSON response
    if request.is_json:
        result = {
            'inputText': text,
            'numReviews': num_reviews,
            'reviews': reviewers,
            'successCount': len(reviewers),
            'errorCount': 0,
            'errors': None
        }
        return jsonify(result)

    return render_template('reviews.html', reviewers=reviewers, text=text)

@app.route('/chat/<int:reviewer_id>')
def chat(reviewer_id):
    """Render chat page for a specific reviewer"""
    from neuralseek_client import REVIEWER_PERSONAS
    
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
    from neuralseek_client import REVIEWER_PERSONAS
    
    data = request.get_json()
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400
    
    # Get reviewer persona
    if 1 <= reviewer_id <= len(REVIEWER_PERSONAS):
        persona = REVIEWER_PERSONAS[reviewer_id - 1]
    else:
        persona = REVIEWER_PERSONAS[0]  # Default to first persona
    
    # Build prompt for NeuralSeek
    prompt = f"{persona['persona']}\n\nUser question: {user_message}\n\nProvide a response as this reviewer would."
    
    # Call NeuralSeek API
    if NEURALSEEK_API_KEY:
        response, error = call_neuralseek_api(prompt)
        if not response:
            response = "I'm having trouble processing that right now. Please try again later."
    else:
        # Fallback dummy response
        response = "I understand your question. Let me think about that... Based on my review, I think your idea has potential but needs refinement in certain areas."
    
    return jsonify({'response': response})


@app.route('/summarize_feedback', methods=['POST'])
def summarize_feedback():
    import os

    try:
        import google.generativeai as genai  # type: ignore
    except ImportError as exc:  # pragma: no cover - import guard
        app.logger.error("Gemini SDK unavailable: %s", exc)
        return jsonify({"items": []})

    data = request.get_json(force=True) or {}
    conversation = data.get("conversation", "")

    if isinstance(conversation, list):
        conversation = "\n".join(str(item) for item in conversation)
    conversation = conversation.strip()

    if not conversation:
        return jsonify({"items": []})

    api_key = os.getenv("GEMINI_API_KEY")
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
    from neuralseek_client import generate_reviewers, REVIEWER_PERSONAS, create_dummy_reviewer

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

