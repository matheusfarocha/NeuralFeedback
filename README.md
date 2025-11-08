# NeuralFeedback

A Flask web application for generating reviews with customizable parameters.

## Features

- Text input for review content
- Slider control for number of reviews (1-20)
- Modern, responsive UI with black theme

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
   - Create a `.env` file in the root directory
   - Add your API keys to the `.env` file:
   ```
   API_KEY=your_api_key_here
   OPENAI_API_KEY=your_openai_api_key_here
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
3. Click "Generate" to process your request

## Environment Variables

The application uses environment variables for API keys. Create a `.env` file in the root directory with your API keys:

```
API_KEY=your_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

Access these in your code using:
```python
import os
api_key = os.getenv('API_KEY')
```

