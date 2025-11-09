"""
NeuralSeek API Client for NeuralFeedback
This module handles communication with NeuralSeek API to generate AI reviews.
"""
import os
import requests
from typing import List, Dict, Optional
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# NeuralSeek API Configuration
# These are loaded from .env file or environment variables
NEURALSEEK_API_KEY = os.getenv('NEURALSEEK_API_KEY', '')
NEURALSEEK_API_URL = os.getenv('NEURALSEEK_API_URL', 'https://api.neuralseek.com/v1/seek')
NEURALSEEK_CHAT_URL = os.getenv('NEURALSEEK_CHAT_URL', 'https://api.neuralseek.com/v1/chat')

# Reviewer personas for generating diverse feedback
REVIEWER_PERSONAS = [
    {"name": "Ava", "age": 28, "profession": "Product Designer", "tone": "Positive", "persona": "You are a creative product designer with 8 years of experience. You focus on user experience and design thinking. Provide constructive, positive feedback emphasizing user-centric design."},
    {"name": "Raj", "age": 41, "profession": "Startup Mentor", "tone": "Moderate", "persona": "You are an experienced startup mentor who has advised 50+ startups. You provide balanced, realistic feedback focusing on business viability and market fit."},
    {"name": "Mia", "age": 34, "profession": "Marketing Strategist", "tone": "Harsh", "persona": "You are a direct marketing strategist known for tough but honest feedback. You focus on market positioning, competitive analysis, and go-to-market strategy. Be critical but constructive."},
    {"name": "David", "age": 36, "profession": "Tech Entrepreneur", "tone": "Positive", "persona": "You are a successful tech entrepreneur who has built and sold two companies. You focus on technical feasibility, scalability, and execution strategy. Be optimistic but practical."},
    {"name": "Sarah", "age": 29, "profession": "UX Researcher", "tone": "Moderate", "persona": "You are a UX researcher with expertise in user validation and research methodologies. You emphasize the importance of user research and data-driven decisions."},
    {"name": "James", "age": 45, "profession": "Venture Capitalist", "tone": "Harsh", "persona": "You are a VC partner who evaluates hundreds of pitches. You focus on market size, traction, unit economics, and scalability. Be direct and focus on what's missing."},
    {"name": "Emma", "age": 31, "profession": "Product Manager", "tone": "Positive", "persona": "You are a product manager at a leading tech company. You focus on product vision, roadmap, and execution. Be encouraging and highlight strengths."},
    {"name": "Chris", "age": 38, "profession": "Business Analyst", "tone": "Moderate", "persona": "You are a business analyst specializing in financial modeling and market analysis. You focus on business model, pricing, and financial projections."},
    {"name": "Lisa", "age": 27, "profession": "Design Lead", "tone": "Positive", "persona": "You are a design lead known for beautiful, scalable design systems. You focus on visual design, brand identity, and design scalability."},
    {"name": "Michael", "age": 42, "profession": "Industry Expert", "tone": "Harsh", "persona": "You are an industry expert with 20 years of experience. You've seen many ideas fail and succeed. Be skeptical, focus on validation, and challenge assumptions."}
]


def call_neuralseek_seek(query: str, context: Optional[str] = None) -> Optional[str]:
    """
    Call NeuralSeek Seek API to get an answer.
    
    Args:
        query: The question or query to send to NeuralSeek
        context: Optional context or conversation history
        
    Returns:
        Response text from NeuralSeek, or None if error
    """
    if not NEURALSEEK_API_KEY:
        return None
    
    try:
        headers = {
            'Authorization': f'Bearer {NEURALSEEK_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'query': query,
        }
        
        if context:
            payload['context'] = context
        
        response = requests.post(
            NEURALSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            # Adjust based on actual NeuralSeek API response structure
            return data.get('answer', data.get('response', data.get('text', '')))
        else:
            print(f"NeuralSeek API Error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Error calling NeuralSeek API: {str(e)}")
        return None


def call_neuralseek_chat(messages: List[Dict[str, str]], model: str = "gpt-4o-mini") -> Optional[str]:
    """
    Call NeuralSeek Chat API for conversational interactions.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        model: LLM model to use (default: gpt-4o-mini)
        
    Returns:
        Response text from NeuralSeek, or None if error
    """
    if not NEURALSEEK_API_KEY:
        return None
    
    try:
        headers = {
            'Authorization': f'Bearer {NEURALSEEK_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': model,
            'messages': messages
        }
        
        response = requests.post(
            NEURALSEEK_CHAT_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            # Adjust based on actual NeuralSeek API response structure
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0].get('message', {}).get('content', '')
            return data.get('answer', data.get('response', data.get('text', '')))
        else:
            print(f"NeuralSeek Chat API Error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Error calling NeuralSeek Chat API: {str(e)}")
        return None


def generate_reviewer_feedback(product_idea: str, reviewer_persona: Dict) -> Dict:
    """
    Generate feedback from a specific reviewer persona using NeuralSeek.
    
    Args:
        product_idea: The product idea or business concept to review
        reviewer_persona: Dictionary with reviewer information and persona prompt
        
    Returns:
        Dictionary with reviewer data including generated feedback
    """
    # Create a prompt for the reviewer
    prompt = f"""{reviewer_persona['persona']}

Please review the following product idea or business concept:

{product_idea}

Provide your feedback as this reviewer. Include:
1. Your overall assessment (1-2 sentences)
2. Key strengths (2-3 points)
3. Areas for improvement (2-3 points)
4. A rating from 1-5 stars based on your assessment

Keep your response concise (3-4 paragraphs) and professional. Match your tone to your persona."""
    
    # Call NeuralSeek API
    messages = [
        {"role": "system", "content": reviewer_persona['persona']},
        {"role": "user", "content": prompt}
    ]
    
    feedback_text = call_neuralseek_chat(messages)
    
    # If API call fails, return None to fall back to dummy data
    if not feedback_text:
        return None
    
    # Parse feedback to extract rating (simple heuristic)
    stars = extract_rating_from_feedback(feedback_text)
    
    return {
        "id": REVIEWER_PERSONAS.index(reviewer_persona) + 1,
        "name": reviewer_persona["name"],
        "age": reviewer_persona["age"],
        "profession": reviewer_persona["profession"],
        "tone": reviewer_persona["tone"],
        "stars": stars,
        "feedback": feedback_text
    }


def extract_rating_from_feedback(feedback: str) -> int:
    """
    Extract a star rating (1-5) from feedback text.
    Simple heuristic - can be improved with better parsing.
    """
    feedback_lower = feedback.lower()
    
    # Look for explicit rating mentions
    if "5 star" in feedback_lower or "five star" in feedback_lower or "5/5" in feedback_lower:
        return 5
    if "4 star" in feedback_lower or "four star" in feedback_lower or "4/5" in feedback_lower:
        return 4
    if "3 star" in feedback_lower or "three star" in feedback_lower or "3/5" in feedback_lower:
        return 3
    if "2 star" in feedback_lower or "two star" in feedback_lower or "2/5" in feedback_lower:
        return 2
    if "1 star" in feedback_lower or "one star" in feedback_lower or "1/5" in feedback_lower:
        return 1
    
    # Heuristic based on tone keywords
    positive_words = ["excellent", "great", "outstanding", "strong", "promising", "innovative"]
    negative_words = ["weak", "unclear", "questionable", "missing", "lacks", "needs improvement"]
    
    positive_count = sum(1 for word in positive_words if word in feedback_lower)
    negative_count = sum(1 for word in negative_words if word in feedback_lower)
    
    if positive_count > negative_count + 2:
        return 5
    elif positive_count > negative_count:
        return 4
    elif positive_count == negative_count:
        return 3
    elif negative_count > positive_count:
        return 2
    else:
        return 1


def generate_reviews(product_idea: str, num_reviewers: int = 5, use_api: bool = True) -> List[Dict]:
    """
    Generate reviews from multiple reviewers using NeuralSeek API.
    
    Args:
        product_idea: The product idea or business concept to review
        num_reviewers: Number of reviewers to generate (1-10)
        use_api: Whether to use NeuralSeek API (False falls back to dummy data)
        
    Returns:
        List of reviewer dictionaries with feedback
    """
    reviewers = []
    
    # Limit to available personas
    num_reviewers = min(num_reviewers, len(REVIEWER_PERSONAS))
    
    for i in range(num_reviewers):
        persona = REVIEWER_PERSONAS[i]
        
        if use_api and NEURALSEEK_API_KEY:
            reviewer = generate_reviewer_feedback(product_idea, persona)
            if reviewer:
                reviewers.append(reviewer)
            else:
                # Fall back to dummy data if API fails
                reviewers.append(create_dummy_reviewer(persona))
        else:
            # Use dummy data if API is not configured
            reviewers.append(create_dummy_reviewer(persona))
    
    return reviewers


def create_dummy_reviewer(persona: Dict) -> Dict:
    """Create dummy reviewer data when API is not available."""
    dummy_feedback = {
        "Positive": "Great idea with strong user focus. The concept shows promise and addresses real user needs. I particularly appreciate the attention to user experience and the innovative approach to solving the problem.",
        "Moderate": "Needs clearer business model. While the idea is interesting, the monetization strategy and target market need more definition. Consider refining your value proposition.",
        "Harsh": "Unclear audience targeting. The market positioning is weak and the competitive landscape analysis is missing. You need to differentiate more clearly from existing solutions."
    }
    
    return {
        "id": REVIEWER_PERSONAS.index(persona) + 1,
        "name": persona["name"],
        "age": persona["age"],
        "profession": persona["profession"],
        "tone": persona["tone"],
        "stars": 5 if persona["tone"] == "Positive" else (3 if persona["tone"] == "Moderate" else 2),
        "feedback": dummy_feedback.get(persona["tone"], dummy_feedback["Moderate"])
    }


def generate_reviewers(product_idea: str, num_reviewers: int = 5) -> List[Dict]:
    """
    Convenience wrapper to generate reviewers using the NeuralSeek API client.
    """
    return generate_reviews(product_idea, num_reviewers=num_reviewers, use_api=True)
