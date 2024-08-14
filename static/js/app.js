document.addEventListener('DOMContentLoaded', () => {
    // Handle the matching system
    const matchForm = document.getElementById('match-form'); // Ensure this ID matches the form ID in your HTML
    const matchResults = document.getElementById('match-list'); // Ensure this ID matches the results container ID in your HTML

    if (matchForm) {
        matchForm.addEventListener('submit', (event) => {
            event.preventDefault();
            const language = document.getElementById('language').value;
            const parentAge = document.getElementById('parent-age').value;
            const childAge = document.getElementById('child-age').value;
            const diagnosis = document.getElementById('diagnosis').value;

            fetch('/api/match', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    language,
                    parent_age: parseInt(parentAge),
                    child_age: parseInt(childAge),
                    diagnosis
                })
            })
            .then(response => response.json())
            .then(users => {
                matchResults.innerHTML = '';
                if (users.length === 0) {
                    matchResults.innerHTML = '<li>No matches found.</li>';
                } else {
                    users.forEach(user => {
                        const userElement = document.createElement('li');
                        userElement.classList.add('match-item');
                        userElement.innerHTML = `
                            <h3>${user.name}</h3>
                            <p>Child Age: ${user.child_age} years old</p>
                            <p><a href="/contact/${user.id}">Contact ${user.name}</a></p>
                        `;
                        matchResults.appendChild(userElement);
                    });
                }
            })
            .catch(error => console.error('Error fetching matches:', error));
        });
    }

    // Handle chat functionality
    const chatBox = document.getElementById('chat-box');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');

    if (chatBox) {
        const chatId = chatBox.getAttribute('data-chat-id'); // Ensure this data attribute is set in your HTML

        function loadMessages() {
            fetch(`/api/chat/${chatId}`)
                .then(response => response.json())
                .then(messages => {
                    chatBox.innerHTML = '';
                    messages.forEach(msg => {
                        const messageElement = document.createElement('p');
                        messageElement.textContent = `${msg.sender}: ${msg.message}`;
                        chatBox.appendChild(messageElement);
                    });
                })
                .catch(error => console.error('Error fetching messages:', error));
        }

        function sendMessage() {
            const message = messageInput.value;
            fetch(`/api/chat/${chatId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sender: 'current_user', // Replace with the actual sender's username
                    message
                })
            })
            .then(response => response.json())
            .then(msg => {
                const messageElement = document.createElement('p');
                messageElement.textContent = `${msg.sender}: ${msg.message}`;
                chatBox.appendChild(messageElement);
                messageInput.value = '';
            })
            .catch(error => console.error('Error sending message:', error));
        }

        sendButton.addEventListener('click', sendMessage);

        loadMessages(); // Load messages on page load
    }
});



