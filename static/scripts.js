const conversationHistory = [];
const feedbackItemSet = new Set();

let feedbackListEl = null;
let applyButton = null;
let isSummarizingFeedback = false;

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

    feedbackListEl = document.getElementById('feedback-dashboard-list');
    applyButton = document.getElementById('applyButton');

    const initialFeedbackScript = document.getElementById('initial-feedback-items');
    let initialFeedbackItems = [];

    if (initialFeedbackScript) {
        try {
            initialFeedbackItems = JSON.parse(initialFeedbackScript.textContent || '[]');
        } catch (error) {
            console.error('Failed to parse initial feedback items', error);
        }
    }

    if (feedbackListEl) {
        const existingItems = feedbackListEl.querySelectorAll('.feedback-item');
        existingItems.forEach(item => {
            const storedInput = item.querySelector('.feedback-checkbox');
            const value = storedInput ? (storedInput.dataset.text || storedInput.value || '') : (item.getAttribute('data-item') || item.textContent || '');
            if (value) {
                feedbackItemSet.add(value.toLowerCase());
            }
        });

        if (Array.isArray(initialFeedbackItems)) {
            initialFeedbackItems.forEach(item => appendFeedbackItem(item));
        }
    }

    initializeConversationHistory();

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

    if (applyButton && feedbackListEl) {
        applyButton.addEventListener('click', handleApplyFeedback);
    }
});

function initializeConversationHistory() {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;

    const messages = chatMessages.querySelectorAll('.message');
    messages.forEach(message => {
        const isAi = message.classList.contains('message-ai');
        const content = (message.textContent || '').trim();
        if (content) {
            recordConversationEntry(content, isAi ? 'ai' : 'user');
        }
    });
}

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

    recordConversationEntry(text, type);

    if (type === 'ai') {
        requestFeedbackSummary();
    }

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function recordConversationEntry(text, type) {
    const normalized = (text || '').trim();
    if (!normalized) return;

    const role = type === 'ai' ? 'reviewer' : 'user';
    conversationHistory.push({ role, content: normalized });

    if (conversationHistory.length > 100) {
        conversationHistory.splice(0, conversationHistory.length - 100);
    }
}

async function requestFeedbackSummary() {
    if (!feedbackListEl || isSummarizingFeedback) return;

    const conversationSnippet = buildConversationSnippet(6);
    if (!conversationSnippet) return;

    isSummarizingFeedback = true;

    try {
        const response = await fetch('/summarize_feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ conversation: conversationSnippet })
        });

        const rawText = await response.text();
        let data = null;

        try {
            data = rawText ? JSON.parse(rawText) : null;
        } catch (jsonErr) {
            console.error('Error summarizing feedback', jsonErr);
            console.error('Raw response:', rawText);
            return;
        }

        if (!response.ok) {
            console.error(data?.error || 'Failed to summarize feedback');
            return;
        }

        if (data && Array.isArray(data.items)) {
            data.items.forEach(item => appendFeedbackItem(item));
        }
    } catch (error) {
        console.error('Error summarizing feedback', error);
    } finally {
        isSummarizingFeedback = false;
    }
}

function buildConversationSnippet(limit) {
    if (!conversationHistory.length) return '';

    const recent = conversationHistory.slice(-limit);
    return recent
        .map(entry => {
            const speaker = entry.role === 'user' ? 'User' : 'Reviewer';
            return `${speaker}: ${entry.content}`;
        })
        .join('\n');
}

function appendFeedbackItem(item) {
    if (!feedbackListEl) return;

    const normalized = (item || '').trim();
    if (!normalized) return;

    const key = normalized.toLowerCase();
    if (feedbackItemSet.has(key)) return;

    feedbackItemSet.add(key);

    const label = document.createElement('label');
    label.className = 'feedback-item';
    label.setAttribute('data-item', normalized);

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'feedback-checkbox';
    checkbox.dataset.text = normalized;
    checkbox.value = normalized;

    const span = document.createElement('span');
    span.textContent = normalized;

    label.appendChild(checkbox);
    label.appendChild(span);

    feedbackListEl.appendChild(label);
}

function collectSelectedFeedbackItems() {
    if (!feedbackListEl) return [];

    return Array.from(
        feedbackListEl.querySelectorAll('.feedback-checkbox:checked')
    )
        .map(input => ((input.dataset && input.dataset.text) || input.value || '').trim())
        .filter(Boolean);
}

async function handleApplyFeedback() {
    const selectedItems = collectSelectedFeedbackItems();

    if (!selectedItems.length) {
        window.alert('Select at least one feedback item to apply.');
        return;
    }

    if (!applyButton) return;

    applyButton.disabled = true;
    applyButton.classList.add('is-loading');
    const originalText = applyButton.textContent;
    applyButton.textContent = 'Applying...';

    try {
        const response = await fetch('/apply_feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ selected_items: selectedItems })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            window.alert('Changes applied! Regenerating feedback...');
            window.location.href = '/generate';
        } else {
            window.alert(data.error || 'Failed to apply feedback. Please try again.');
        }
    } catch (error) {
        console.error('Error applying feedback', error);
        window.alert('Failed to apply feedback. Please try again.');
    } finally {
        applyButton.disabled = false;
        applyButton.classList.remove('is-loading');
        applyButton.textContent = originalText;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

