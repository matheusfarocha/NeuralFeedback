// Slider value update for index page
document.addEventListener('DOMContentLoaded', function() {
    const slider = document.getElementById('num_reviewers');
    const sliderValue = document.getElementById('sliderValue');
    
    if (slider && sliderValue) {
        slider.addEventListener('input', function() {
            sliderValue.textContent = this.value;
        });
    }

    // Reviewer card click handlers
    const reviewerCards = document.querySelectorAll('.reviewer-card[data-reviewer-id]');
    reviewerCards.forEach(card => {
        card.addEventListener('click', function() {
            const reviewerId = this.getAttribute('data-reviewer-id');
            window.location.href = `/chat/${reviewerId}`;
        });
    });

    // Chat form submission handler
    const chatForm = document.getElementById('chatForm');
    const messageInput = document.getElementById('messageInput');
    const chatMessages = document.getElementById('chatMessages');

    if (chatForm && messageInput && chatMessages) {
        chatForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const message = messageInput.value.trim();
            if (!message) return;

            // Add user message
            addMessage(message, 'user');
            messageInput.value = '';
            messageInput.disabled = true;

            // Get reviewer ID from URL
            const pathParts = window.location.pathname.split('/').filter(p => p);
            const reviewerId = pathParts[pathParts.length - 1]; // /chat/1 -> 1

            try {
                // Call Flask API endpoint
                const response = await fetch(`/chat/${reviewerId}/message`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ message: message })
                });

                const data = await response.json();
                
                if (response.ok) {
                    addMessage(data.response, 'ai');
                } else {
                    addMessage(data.error || 'Error sending message', 'ai');
                }
            } catch (error) {
                addMessage('Error: Could not send message. Please try again.', 'ai');
            } finally {
                messageInput.disabled = false;
                messageInput.focus();
            }
        });
    }
});

function addMessage(text, type) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;

    const messageDiv = document.createElement('div');
    messageDiv.className = `message message-${type}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = `<p>${escapeHtml(text)}</p>`;
    
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

