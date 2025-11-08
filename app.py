from flask import Flask, render_template, request, redirect, url_for, jsonify
from dotenv import load_dotenv
import os
import requests

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

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


@app.route('/generate', methods=['POST'])
def generate():
    """Handle form submission and generate multiple reviews using NeuralSeek API"""
    # Support both form data and JSON
    if request.is_json:
        data = request.get_json()
        text = data.get('text', '').strip()
        num_reviews = int(data.get('numReviews', 5))
    else:
        # Form-based submission (from styled frontend)
        text = request.form.get('text_input', '').strip()
        num_reviews = int(request.form.get('num_reviewers', 5))
    
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
    
    reviews = []
    errors = []
    
    # Generate multiple reviews with slightly different prompts
    for i in range(num_reviews):
        # Create a variation of the prompt for each review
        varied_prompt = generate_review_variation(text, i)
        
        # Call NeuralSeek API
        review, error = call_neuralseek_api(varied_prompt)
        
        if review:
            reviews.append({
                'index': i + 1,
                'review': review,
                'prompt': varied_prompt
            })
        else:
            errors.append(f"Review {i + 1}: {error}")
    
    # If JSON request, return JSON response
    if request.is_json:
        if not reviews:
            return jsonify({
                'error': 'Failed to generate any reviews',
                'details': errors
            }), 500
        
        result = {
            'inputText': text,
            'numReviews': num_reviews,
            'reviews': reviews,
            'successCount': len(reviews),
            'errorCount': len(errors),
            'errors': errors if errors else None
        }
        return jsonify(result)
    
    # If form request, render reviews page with reviewer data
    # Convert reviews to reviewer format for the reviews.html template
    from neuralseek_client import REVIEWER_PERSONAS, extract_rating_from_feedback
    
    reviewers = []
    for i, review_data in enumerate(reviews):
        if i < len(REVIEWER_PERSONAS):
            persona = REVIEWER_PERSONAS[i]
            feedback = review_data.get('review', '')
            stars = extract_rating_from_feedback(feedback) if feedback else 3
            
            reviewers.append({
                "id": i + 1,
                "name": persona["name"],
                "age": persona["age"],
                "profession": persona["profession"],
                "tone": persona["tone"],
                "stars": stars,
                "feedback": feedback
            })
    
    # If no reviews generated, use dummy data
    if not reviewers:
        from neuralseek_client import create_dummy_reviewer
        reviewers = [create_dummy_reviewer(REVIEWER_PERSONAS[i]) for i in range(min(num_reviews, len(REVIEWER_PERSONAS)))]
    
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
    
    return render_template('chat.html', reviewer=reviewer, reviewer_id=reviewer_id)

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

if __name__ == '__main__':
    app.run(debug=True)

