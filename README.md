# NeuralFeedback

A Flask web application that generates persona-based reviewer feedback using the NeuralSeek API, with optional Gemini summarization for chat insights.

## Features

- Text area for describing a product or idea
- Slider to choose how many reviewers to generate (1-10)
- Persona-driven reviewer cards with tone, rating, and feedback
- Live chat per reviewer with automatic feedback summarization
- Glassmorphism-inspired dark UI styling responsive across devices

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables (create a `.env` file in the project root):
   ```
   NEURALSEEK_API_KEY=your_neuralseek_api_key
   FLASK_SECRET_KEY=choose_a_secure_secret
   # Optional: enable Gemini-powered feedback summaries
   GEMINI_API_KEY=your_gemini_api_key
   ```
   > The `.env` file is already ignored by Git—never commit secrets.

3. Start the Flask development server:
```bash
python app.py
```

4. Open the app in your browser:
```
http://localhost:5000
```

## Usage

1. Describe your product idea in the text area.
2. Choose how many reviewer personas you want.
3. Submit the form to generate feedback cards.
4. Click a reviewer to open a chat, ask follow-up questions, and apply summarized feedback.

## Environment Variables

- `NEURALSEEK_API_KEY` (required): enables NeuralSeek reviewer generation and chat responses.
- `GEMINI_API_KEY` (optional): enables chat feedback summarization via Google Gemini.
- `FLASK_SECRET_KEY` (required): secures Flask sessions used for storing feedback state.

Gemini keys can be created on [Google AI Studio](https://makersuite.google.com/app/apikey); NeuralSeek keys are available from the NeuralSeek dashboard.
