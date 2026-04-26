const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const messagesContainer = document.getElementById('messages-container');
const clearBtn = document.getElementById('clear-btn');

// Local Storage Key
const STORAGE_KEY = 'emotional_advisor_chat_history';

// Adjust textarea height automatically
chatInput.addEventListener('input', function() {
    this.style.height = '24px'; // Reset height
    const newHeight = Math.min(this.scrollHeight, 300);
    this.style.height = newHeight + 'px';
    
    // If we hit the max height, allow scrolling just in case it gets really huge
    if (this.scrollHeight > 300) {
        this.style.overflowY = 'auto';
    } else {
        this.style.overflowY = 'hidden';
    }
});

// Handle Enter to send (Shift+Enter for new line)
chatInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

sendBtn.addEventListener('click', sendMessage);
clearBtn.addEventListener('click', () => {
    // Check if welcome container exists before clearing
    const hasWelcome = document.querySelector('.welcome-container') !== null;
    
    // Clear localStorage
    localStorage.removeItem(STORAGE_KEY);
    
    if (hasWelcome) {
        // Just clear regular messages, leave welcome container
        const messages = document.querySelectorAll('.message');
        messages.forEach(msg => msg.remove());
        const welcome = document.querySelector('.welcome-container');
        if (welcome) welcome.style.display = 'flex';
    } else {
        // If welcome container is completely gone, just clear everything
        messagesContainer.innerHTML = '';
    }
});

let thoughtEventSource = null;

// Connect to SSE stream on load
function connectThoughtStream() {
    if (thoughtEventSource) {
        thoughtEventSource.close();
    }
    
    thoughtEventSource = new EventSource('/api/thoughts/stream');
    
    thoughtEventSource.addEventListener('thought', (e) => {
        const typingEl = document.querySelector('.typing-indicator');
        if (typingEl) {
            // Update typing indicator with thought
            const thoughtText = e.data;
            typingEl.innerHTML = `
                <div class="thought-spinner"></div>
                <span class="thought-text">${thoughtText}</span>
            `;
        }
    });
    
    thoughtEventSource.onerror = (err) => {
        console.log('SSE connection error, attempting to reconnect...');
        thoughtEventSource.close();
        setTimeout(connectThoughtStream, 3000);
    };
}

// Initialize SSE connection
connectThoughtStream();

// Helper function to fill input from suggestion chips
function fillInput(text) {
    chatInput.value = text;
    chatInput.focus();
    
    // Check if there's a placeholder "xxx" and select it for easy replacement
    const placeholderIndex = text.indexOf('xxx');
    if (placeholderIndex !== -1) {
        chatInput.setSelectionRange(placeholderIndex, placeholderIndex + 3);
    }
    
    // Auto adjust height
    chatInput.style.height = '24px';
    const newHeight = Math.min(chatInput.scrollHeight, 300);
    chatInput.style.height = newHeight + 'px';
    chatInput.style.overflowY = 'hidden';
}

async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    // Reset input
    chatInput.value = '';
    chatInput.style.height = '24px';

    // Add user message to UI
    addMessageToUI(text, 'user-message');

    // Show typing indicator
    const typingId = showTypingIndicator();

    try {
        // Send to backend API
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: text })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        
        // Remove typing indicator
        removeMessage(typingId);

        // Add bot message
        addMessageToUI(data.response, 'bot-message');

    } catch (error) {
        console.error("Error sending message:", error);
        removeMessage(typingId);
        addMessageToUI("❌ 连接服务器失败，请检查 Agent 是否正常运行。", 'system-message');
    }
}

function addMessageToUI(text, className, saveToStorage = true) {
    // Hide welcome container if it exists
    const welcomeContainer = document.querySelector('.welcome-container');
    if (welcomeContainer) {
        welcomeContainer.style.display = 'none';
    }

    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${className}`;
    
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    
    if (className === 'bot-message') {
        // Parse markdown for bot response
        bubble.innerHTML = marked.parse(text);
    } else {
        // Plain text for user/system
        bubble.textContent = text;
    }
    
    msgDiv.appendChild(bubble);
    messagesContainer.appendChild(msgDiv);
    
    // Save to localStorage
    if (saveToStorage && (className === 'user-message' || className === 'bot-message')) {
        saveMessageToStorage(text, className);
    }
    
    // Auto scroll to bottom
    scrollToBottom();
}

function saveMessageToStorage(text, className) {
    try {
        const history = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        history.push({ text, className });
        localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
    } catch (e) {
        console.error('Failed to save chat history to localStorage', e);
    }
}

function loadHistoryFromStorage() {
    try {
        const history = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        if (history.length > 0) {
            history.forEach(msg => {
                addMessageToUI(msg.text, msg.className, false);
            });
        }
    } catch (e) {
        console.error('Failed to load chat history from localStorage', e);
    }
}

// Load history on startup
document.addEventListener('DOMContentLoaded', loadHistoryFromStorage);

function showTypingIndicator() {
    const id = 'typing-' + Date.now();
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message bot-message';
    msgDiv.id = id;
    
    const bubble = document.createElement('div');
    bubble.className = 'bubble typing-indicator';
    bubble.innerHTML = `
        <div class="typing-dots-container">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        </div>
        <span class="thought-text">正在处理...</span>
    `;
    
    msgDiv.appendChild(bubble);
    messagesContainer.appendChild(msgDiv);
    scrollToBottom();
    
    return id;
}

function removeMessage(id) {
    const el = document.getElementById(id);
    if (el) {
        el.remove();
    }
}

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}
