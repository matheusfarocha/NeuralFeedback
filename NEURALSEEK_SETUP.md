# NeuralSeek Integration Setup Guide

This guide will help you integrate NeuralSeek API with NeuralFeedback to generate AI-powered reviews.

## Overview

NeuralSeek is an AI-powered Answers-as-a-Service platform that can be used to generate intelligent feedback on product ideas and business concepts. According to the [NeuralSeek Documentation](https://documentation.neuralseek.com/#overview), NeuralSeek provides:

- **Seek API**: For querying and getting answers
- **Chat API**: For conversational interactions
- **Multiple LLM Support**: Including GPT-4o mini
- **REST API & WebHooks**: For easy integration

## Setup Steps

### 1. Get NeuralSeek Access

NeuralSeek is available as SaaS on multiple platforms:
- **IBM Cloud**: https://cloud.ibm.com/catalog/services/neuralseek
- **AWS Marketplace**: https://aws.amazon.com/marketplace/seller-profile?id=fd9c4578-de8c-4905-a30e-fe9e9fd31f46
- **Azure Marketplace**: https://azuremarketplace.microsoft.com/en-us/marketplace/apps/3ba02973-0aa1-4044-9659-7f17829d9d8d.neuralseek

Choose the platform that works best for you and sign up for a NeuralSeek account.

### 2. Configure NeuralSeek

1. Navigate to the NeuralSeek dashboard
2. Go to the **Configure** tab
3. Add **GPT-4o mini** as your LLM model
4. Enter your OpenAI API key (or configure the model of your choice)
5. Test the connection to ensure it's working

### 3. Get API Credentials

1. In your NeuralSeek dashboard, navigate to **Integrate** section
2. Find your **API Key** or **Access Token**
3. Note your NeuralSeek API endpoint URL (this varies by deployment)

### 4. Configure Environment Variables

Create a `.env` file in your project root (or set environment variables):

```bash
# NeuralSeek API Configuration
NEURALSEEK_API_KEY=your_api_key_here
NEURALSEEK_API_URL=https://your-instance.neuralseek.com/v1/seek
NEURALSEEK_CHAT_URL=https://your-instance.neuralseek.com/v1/chat
```

**Important**: The exact API endpoints may vary based on your NeuralSeek deployment. Check your NeuralSeek documentation for the correct endpoints.

### 5. Install Dependencies

The required dependencies are already in `requirements.txt`:

```bash
pip install -r requirements.txt
```

This installs:
- Flask (web framework)
- requests (for API calls)

### 6. Update API Endpoints (if needed)

If your NeuralSeek deployment uses different endpoint URLs, update them in `neuralseek_client.py`:

```python
NEURALSEEK_API_URL = os.getenv('NEURALSEEK_API_URL', 'https://your-endpoint/v1/seek')
NEURALSEEK_CHAT_URL = os.getenv('NEURALSEEK_CHAT_URL', 'https://your-endpoint/v1/chat')
```

### 7. Test the Integration

1. Start your Flask app: `python app.py`
2. Navigate to `http://localhost:5000`
3. Enter a product idea and generate reviews
4. Check the console for any API errors

## How It Works

### Review Generation

When a user submits a product idea:

1. The app calls `generate_reviews()` from `neuralseek_client.py`
2. For each reviewer persona, it creates a prompt with:
   - The reviewer's persona and expertise
   - The product idea to review
3. The prompt is sent to NeuralSeek Chat API
4. NeuralSeek generates personalized feedback based on the persona
5. The feedback is parsed and displayed in reviewer cards

### Chat Interface

When chatting with a reviewer:

1. User messages are sent to `/chat/<reviewer_id>/message` endpoint
2. The endpoint calls NeuralSeek Chat API with the reviewer's persona
3. NeuralSeek generates a contextual response
4. The response is displayed in the chat interface

## Fallback Behavior

If NeuralSeek API is not configured or unavailable:

- The app automatically falls back to dummy/placeholder data
- Reviews will still be generated, but with static content
- Chat will use simple dummy responses

This ensures the app works even without API credentials for development/testing.

## Troubleshooting

### API Not Working

1. **Check API Key**: Verify your `NEURALSEEK_API_KEY` is set correctly
2. **Check Endpoints**: Ensure the API URLs match your NeuralSeek deployment
3. **Check Network**: Verify you can reach the NeuralSeek API from your server
4. **Check Logs**: Look for error messages in the Flask console

### Response Format Issues

The NeuralSeek API response format may vary. If responses aren't parsing correctly:

1. Check the actual API response structure
2. Update the parsing logic in `neuralseek_client.py`:
   - `call_neuralseek_seek()` - for Seek API responses
   - `call_neuralseek_chat()` - for Chat API responses

### Rate Limiting

If you encounter rate limits:

- NeuralSeek may have usage limits based on your plan
- Consider implementing request queuing or caching
- Add retry logic with exponential backoff

## Additional Resources

- **NeuralSeek Documentation**: https://documentation.neuralseek.com/
- **NeuralSeek Academy**: https://academy.neuralseek.com/
- **NeuralSeek Labs**: https://labs.neuralseek.com/
- **Schedule a Demo**: https://neuralseek.com/demo

## Next Steps

Once the basic integration is working:

1. **Fine-tune Personas**: Adjust reviewer personas in `neuralseek_client.py` for better feedback
2. **Add Context**: Pass conversation history to maintain context in chat
3. **Improve Parsing**: Enhance rating extraction from feedback text
4. **Add Caching**: Cache responses to reduce API calls
5. **Error Handling**: Add better error messages and retry logic

