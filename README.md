# NeuralFeedback

A Flask web application for generating reviews with customizable parameters using Google Gemini API.

## Features

- Text input for review content
- Slider control for number of reviews (1-20)
- Age range selector (dual-range slider)
- Gender and location dropdowns for context
- Modern, responsive UI with black theme
- AI-powered review generation with personality traits (energetic, critical, logical, emotional, etc.)

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
   - Create a `.env` file in the root directory
   - Add your Gemini API key to the `.env` file:
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   ```
   - **Never commit the `.env` file to version control** (it's already in `.gitignore`)

3. Run the Flask application:
```bash
python app.py
```

4. Open your browser and navigate to:
```
http://localhost:5000
```

## Usage

1. Enter text in the text input field
2. Adjust the number of reviews using the slider
3. Set age range, gender, and location (optional context)
4. Click "Generate" to generate multiple review variations with different personality traits

## Environment Variables

The application uses environment variables for API keys. Create a `.env` file in the root directory with your Gemini API key:

```
GEMINI_API_KEY=your_gemini_api_key_here
```

You can get a Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey).

