from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    """Handle form submission and return results"""
    data = request.get_json()
    
    text = data.get('text', '').strip()
    num_reviews = int(data.get('numReviews', 5))
    
    if not text:
        return jsonify({'error': 'Please enter some text first!'}), 400
    
    # Process the data (you can add your review generation logic here)
    result = {
        'inputText': text,
        'numReviews': num_reviews,
        'message': f'Ready to generate {num_reviews} reviews.'
    }
    
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)

