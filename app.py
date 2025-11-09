from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
import os


import re
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import google.generativeai as genai  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    genai = None  # type: ignore[assignment]

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")

# Load Gemini API key from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini API when available
if genai and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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

    context_parts = []

    if age_min and age_max:
        context_parts.append(f"age {age_min}-{age_max}")
    elif age_min:
        context_parts.append(f"age {age_min}+")
    elif age_max:
        context_parts.append(f"age up to {age_max}")
    if gender:
        context_parts.append(f"gender {gender}")
    if location:
        context_parts.append(f"from {location}")

    reviewer_context = f"a potential customer who is {personality}"
    if context_parts:
        reviewer_context += f", {', '.join(context_parts)}"


    gemini_prompt = f"""
You are a potential customer responding to a product idea.
The product concept is: {prompt}

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

        metadata = {
            "persona_name": None,  # Assigned later
            "persona_descriptor": reviewer_context,
            "characteristics": selected_characteristics,
            "characteristic_intensities": characteristic_intensities,


            "sentiment_rating": rating,
            "personality_description": personality,
            "age_range": f"{age_min}-{age_max}" if age_min and age_max else None,
            "gender": gender or None,
            "location": location or None,
        }

        return {"text": review_text, "metadata": metadata}, None
    except Exception as exc:  # pragma: no cover - network failure
        print("🔥 Error generating review:", exc)

        traceback.print_exc()
        return None, f"Gemini error: {exc}"


@app.route("/generate", methods=["POST"])
def generate():
    """Handle frontend POST to generate multiple feedbacks."""
    try:
        data = request.get_json(silent=True) or {}
        print("\n✅ Received data from frontend:", data)

        text = (data.get("text") or "").strip()
        num_reviews = max(1, min(20, int(data.get("numReviews", 5))))


        selected_characteristics = data.get("characteristics", [])
        age_min = data.get("ageMin")
        age_max = data.get("ageMax")
        gender = data.get("gender")
        location = data.get("location")

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
                    }
                ),
                500,
            )

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
                }
            )

        reviews, errors = [], []

        with ThreadPoolExecutor(max_workers=min(10, num_reviews)) as executor:
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
                ): t
                for t in tasks
            }

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

        reviews.sort(key=lambda item: item["id"])

        if not reviews:
            fallback, message = build_fallback_personas(text, num_reviews, selected_characteristics)
            session["personas"] = fallback
            session.modified = True
            return (
                jsonify(
                    {
                        "error": "No responses generated",
                        "fallback": fallback,
                        "message": message,
                        "details": errors,
                    }
                ),
                500,
            )

        session["personas"] = reviews
        session.modified = True

        result = {
            "inputText": text,
            "numReviews": num_reviews,
            "reviews": reviews,
            "successCount": len(reviews),
            "errorCount": len(errors),
            "errors": errors or None,
        }

        print(f"✅ Successfully generated {len(reviews)} reviews.")
        return jsonify(result)

    except Exception as exc:  # pragma: no cover - unexpected failure
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
                }
            ),
            500,
        )


@app.route("/chat/<int:persona_id>")
def chat(persona_id):
    """Render the chat interface for a specific persona."""
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

    metadata = persona.get("metadata", {})
    persona_name = metadata.get("persona_name") or f"Persona {persona_id}"
    descriptor = metadata.get("persona_descriptor") or metadata.get("personality_description") or "Customer Persona"
    traits = metadata.get("characteristics", [])
    review_text = persona.get("review", "No review available.")
    sentiment_rating = metadata.get("sentiment_rating")

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
    """Generate a persona-specific chat reply."""
    payload = request.get_json(silent=True) or {}
    user_msg = (payload.get("message") or "").strip()
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    personas = session.get("personas", [])
    persona = next((p for p in personas if p.get("id") == persona_id), None)
    if not persona:
        return jsonify({"error": "Persona not found in session"}), 404

    metadata = persona.get("metadata", {})
    tone_description = metadata.get("persona_descriptor") or metadata.get("personality_description") or "an insightful customer persona"
    review_summary = persona.get("review", "")

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
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(chat_prompt)
        reply = (response.text or "").strip()
        if not reply:
            reply = "I'm reflecting on that — could you clarify a bit more?"
        return jsonify({"reply": reply})
    except Exception as exc:  # pragma: no cover
        print("🔥 Gemini chat error:", exc)
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


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
    for idx in range(max(1, num_reviewers)):
        template = base_personas[idx % len(base_personas)]
        suffix = idx // len(base_personas) + 1
        persona_name = template["persona_name"]
        if suffix > 1:
            persona_name = f"{persona_name} {suffix}"

        rating = 6 + (idx % 3)  # 6-8 out of 10
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