from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Load Gemini API key from environment variables
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Configure Gemini API
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Define intensity levels for characteristic variations
INTENSITY_LEVELS = [0.9, 1.0, 1.1]  # 90%, 100%, 110%

# Available characteristics for users to select
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
    "adventurous"
]

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html', characteristics=AVAILABLE_CHARACTERISTICS)

def generate_review(prompt, selected_characteristics, characteristic_intensities, age_min=None, age_max=None, gender=None, location=None):
    """
    Generate customer feedback using Gemini API with selected persona characteristics.
    All feedback responses have the same characteristics but with different intensity combinations.

    Args:
        prompt: The product idea/concept to get feedback on
        selected_characteristics: List of characteristic names selected by user
        characteristic_intensities: Dict mapping each characteristic to its intensity (0.9, 1.0, or 1.1)
        age_min, age_max, gender, location: Demographic parameters for the customer persona

    Returns:
        Tuple of (review_data, error) where review_data contains feedback text and persona metadata
    """
    if not GEMINI_API_KEY:
        return None, "Gemini API key not configured"

    if not selected_characteristics:
        return None, "No characteristics selected"

    # Intensity modifier descriptions
    intensity_descriptions = {
        0.9: "somewhat",
        1.0: "moderately",
        1.1: "very"
    }

    # Build the personality description with intensities
    personality_parts = []
    for char in selected_characteristics:
        intensity = characteristic_intensities.get(char, 1.0)
        intensity_modifier = intensity_descriptions.get(intensity, "moderately")
        personality_parts.append(f"{intensity_modifier} {char}")

    # Combine characteristics
    if len(personality_parts) == 1:
        personality = personality_parts[0]
    elif len(personality_parts) == 2:
        personality = f"{personality_parts[0]} and {personality_parts[1]}"
    else:
        personality = ", ".join(personality_parts[:-1]) + f", and {personality_parts[-1]}"

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
        reviewer_context = f"a potential customer who is {personality}, {', '.join(context_parts)}"
    else:
        reviewer_context = f"a potential customer who is {personality}"
    
    # Create the prompt for Gemini
    gemini_prompt = f"""You are a potential customer being presented with a product idea. The product concept is: {prompt}

You are {reviewer_context}.

Please share your honest thoughts and feedback about this product idea. Provide declarative statements about what you think - do NOT ask questions. Explain what appeals to you or concerns you about this concept. Keep your response natural, authentic, and demonstrate your personality traits in your writing style and tone. Provide 2-4 sentences of genuine feedback.

After your feedback, on a new line, provide a rating from 1-10 indicating how positive you feel about this product idea (1 = very negative/would never buy, 10 = very positive/would definitely buy). Format the rating EXACTLY as: RATING: X

Example format:
[Your 2-4 sentences of feedback here]
RATING: 7"""
    
    try:
        # Use gemini-2.0-flash-exp directly
        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        # Generate the review
        response = model.generate_content(gemini_prompt)

        # Extract the review text
        full_response = response.text.strip()

        # Extract rating from response
        import re
        rating_match = re.search(r'RATING:\s*(\d+)', full_response, re.IGNORECASE)

        if rating_match:
            rating = int(rating_match.group(1))
            # Clamp rating between 1 and 10
            rating = max(1, min(10, rating))
            # Remove the rating line from the feedback text
            review_text = re.sub(r'\s*RATING:\s*\d+\s*$', '', full_response, flags=re.IGNORECASE).strip()
        else:
            # If no rating found, default to neutral (5)
            rating = 5
            review_text = full_response

        # Calculate average intensity for display
        avg_intensity = sum(characteristic_intensities.values()) / len(characteristic_intensities)

        # Create metadata for this review
        metadata = {
            'characteristics': selected_characteristics,
            'characteristic_intensities': characteristic_intensities,
            'avg_intensity': avg_intensity,
            'avg_intensity_label': f"{int(avg_intensity * 100)}%",
            'sentiment_rating': rating,
            'personality_description': personality,
            'age_range': f"{age_min}-{age_max}" if age_min and age_max else None,
            'gender': gender if gender else None,
            'location': location if location else None
        }

        review_data = {
            'text': review_text,
            'metadata': metadata
        }

        return review_data, None

    except Exception as e:
        return None, f"Error generating review: {str(e)}"


@app.route('/generate', methods=['POST'])
def generate():
    """Handle form submission and generate customer feedback from multiple AI personas using Gemini API with multi-threading"""
    data = request.get_json()

    text = data.get('text', '').strip()
    num_reviews = int(data.get('numReviews', 5))
    age_min = data.get('ageMin')
    age_max = data.get('ageMax')
    gender = data.get('gender', '').strip()
    location = data.get('location', '').strip()
    selected_characteristics = data.get('characteristics', [])

    if not text:
        return jsonify({'error': 'Please enter a product idea first!'}), 400

    if not selected_characteristics:
        return jsonify({'error': 'Please select at least one characteristic for your customer personas!'}), 400

    if not GEMINI_API_KEY:
        return jsonify({'error': 'Gemini API key not configured'}), 500

    reviews = []
    errors = []

    # Create tasks for multi-threaded generation
    # Each review has the same characteristics but with different intensity combinations
    tasks = []
    for i in range(num_reviews):
        # Create intensity mapping for each characteristic
        # Each characteristic gets its own intensity, cycling through levels
        characteristic_intensities = {}
        for j, char in enumerate(selected_characteristics):
            # Vary intensities across characteristics and reviews
            intensity_index = (i + j) % len(INTENSITY_LEVELS)
            characteristic_intensities[char] = INTENSITY_LEVELS[intensity_index]

        tasks.append({
            'index': i,
            'prompt': text,
            'selected_characteristics': selected_characteristics,
            'characteristic_intensities': characteristic_intensities,
            'age_min': age_min,
            'age_max': age_max,
            'gender': gender,
            'location': location
        })

    # Execute API calls in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(10, num_reviews)) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(
                generate_review,
                task['prompt'],
                task['selected_characteristics'],
                task['characteristic_intensities'],
                task['age_min'],
                task['age_max'],
                task['gender'],
                task['location']
            ): task for task in tasks
        }

        # Collect results as they complete
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                review_data, error = future.result()

                if review_data:
                    reviews.append({
                        'index': task['index'] + 1,
                        'review': review_data['text'],
                        'metadata': review_data['metadata'],
                        'prompt': text
                    })
                else:
                    errors.append(f"Review {task['index'] + 1}: {error}")
            except Exception as e:
                errors.append(f"Review {task['index'] + 1}: Unexpected error - {str(e)}")

    # Sort reviews by index to maintain order
    reviews.sort(key=lambda x: x['index'])

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
