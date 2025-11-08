from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os
import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Load Gemini API key from environment variables
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Configure Gemini API
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

def generate_review(prompt, variation_index, age_min=None, age_max=None, gender=None, location=None):
    """
    Generate a review using Gemini API with personality traits as context.
    Each review has a slightly different personality (energetic, critical, logical, emotional, etc.)
    """
    if not GEMINI_API_KEY:
        return None, "Gemini API key not configured"
    
    # Personality traits that vary for each review
    personality_traits = [
        "slightly more energetic and enthusiastic",
        "slightly more critical and analytical",
        "slightly more logical and methodical",
        "slightly more emotional and expressive",
        "slightly more optimistic and positive",
        "slightly more skeptical and cautious",
        "slightly more detailed and thorough",
        "slightly more concise and direct",
        "slightly more creative and imaginative",
        "slightly more practical and pragmatic",
        "slightly more passionate and intense",
        "slightly more balanced and measured",
        "slightly more curious and exploratory",
        "slightly more experienced and knowledgeable",
        "slightly more casual and relaxed",
        "slightly more formal and professional",
        "slightly more humorous and lighthearted",
        "slightly more serious and focused",
        "slightly more empathetic and understanding",
        "slightly more objective and unbiased"
    ]
    
    # Get personality trait for this variation
    personality = personality_traits[variation_index % len(personality_traits)]
    
    # Build context string if any context is provided
    context_parts = []
    if age_min and age_max:
        if age_min == age_max:
            context_parts.append(f"age {age_min}")
        else:
            context_parts.append(f"age {age_min}-{age_max}")
    elif age_min:
        context_parts.append(f"age {age_min}+")
    elif age_max:
        context_parts.append(f"age up to {age_max}")
    if gender:
        context_parts.append(f"gender {gender}")
    if location:
        context_parts.append(f"from {location}")
    
    # Build the full context string
    if context_parts:
        reviewer_context = f"as a reviewer who is {personality}, {', '.join(context_parts)}"
    else:
        reviewer_context = f"as a reviewer who is {personality}"
    
    # Create the prompt for Gemini
    gemini_prompt = f"""Write a review about: {prompt}

You are writing this review {reviewer_context}. 

Write a sample review that reflects this personality and context. The review should be natural, authentic, and demonstrate the personality trait in the writing style and tone. Keep it concise but meaningful (2-4 sentences)."""
    
    try:
        # Use gemini-2.0-flash-exp directly
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Generate the review
        response = model.generate_content(gemini_prompt)
        
        # Extract the review text
        review_text = response.text.strip()
        
        return review_text, None
        
    except Exception as e:
        return None, f"Error generating review: {str(e)}"


@app.route('/generate', methods=['POST'])
def generate():
    """Handle form submission and generate multiple reviews using Gemini API"""
    data = request.get_json()
    
    text = data.get('text', '').strip()
    num_reviews = int(data.get('numReviews', 5))
    age_min = data.get('ageMin')
    age_max = data.get('ageMax')
    gender = data.get('gender', '').strip()
    location = data.get('location', '').strip()
    
    if not text:
        return jsonify({'error': 'Please enter some text first!'}), 400
    
    if not GEMINI_API_KEY:
        return jsonify({'error': 'Gemini API key not configured'}), 500
    
    reviews = []
    errors = []
    
    # Generate multiple reviews with variations
    for i in range(num_reviews):
        # Generate review using Gemini API with personality traits
        review, error = generate_review(text, i, age_min, age_max, gender, location)
        
        if review:
            reviews.append({
                'index': i + 1,
                'review': review,
                'prompt': text
            })
        else:
            errors.append(f"Review {i + 1}: {error}")
    
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

if __name__ == '__main__':
    app.run(debug=True)

