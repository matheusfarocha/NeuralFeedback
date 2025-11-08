from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import traceback

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


@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html', characteristics=AVAILABLE_CHARACTERISTICS)


def generate_review(prompt, selected_characteristics, characteristic_intensities,
                    age_min=None, age_max=None, gender=None, location=None):
    """Generate single review using Gemini API."""
    if not GEMINI_API_KEY:
        return None, "Gemini API key not configured"
    if not selected_characteristics:
        return None, "No characteristics selected"

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

    # Construct Gemini prompt
    gemini_prompt = f"""You are a potential customer being presented with a product idea.
The product concept is: {prompt}

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
