from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit, join_room, leave_room
import openai
import json
import numpy as np
import joblib
import os
import glob
import re

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with your actual secret key

# Initialize Flask-SocketIO
socketio = SocketIO(app)

# Set your OpenAI API key here
openai.api_key = ''
# Load Q&A data from file
with open(r'/Users/mariammahomed/Desktop/تآزُر/qa_pairs.json', 'r', encoding='utf-8') as file:
    qa_data = json.load(file)

# Load the pre-trained model
model = joblib.load(r'/Users/mariammahomed/Desktop/تآزُر/SGDClassifier.joblib')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_or_signup'

# File paths for storing JSON data
USERS_FILE = 'users.json'
PROFILES_FILE = 'profiles.json'
CHATS_FILE = 'chats.json'

# Load data from JSON file
def load_data(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)
    else:
        return []

# Save data to JSON file
def save_data(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['id']
        self.username = user_data['username']
        self.email = user_data['email']
        self.load_profile()

    def load_profile(self):
        profiles = load_data(PROFILES_FILE)
        profile = next((profile for profile in profiles if profile['user_id'] == self.id), None)
        if profile:
            self.language = profile.get('language')
            self.parent_age = profile.get('parent_age')
            self.gender = profile.get('gender')
            self.child_age = profile.get('child_age')
            self.diagnosis = profile.get('diagnosis')
            self.region = profile.get('region')

@login_manager.user_loader
def load_user(user_id):
    users = load_data(USERS_FILE)
    user_data = next((user for user in users if user['id'] == int(user_id)), None)
    if user_data:
        return User(user_data)
    return None

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('home.html')

@app.route('/conditions')
def conditions():
    return render_template('conditions.html')

@app.route('/index')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login_or_signup():
    if request.method == 'POST':
        action = request.form.get('action')
        users = load_data(USERS_FILE)

        if action == 'login':
            username = request.form['username']
            password = request.form['password']

            # Load the user by username
            user = next((user for user in users if user['username'] == username), None)

            if user and check_password_hash(user['password'], password):
                user_obj = User(user)
                login_user(user_obj)
                return redirect(url_for('index'))
            else:
                flash('Invalid credentials')  # Notify user of invalid credentials

        elif action == 'signup':
            email = request.form['email']
            username = request.form['username']
            password = generate_password_hash(request.form['password'])

            new_user = {
                'id': len(users) + 1,  # Auto-increment ID
                'username': username,
                'email': email,
                'password': password
            }

            users.append(new_user)
            save_data(USERS_FILE, users)
            flash('Signup successful! You can now log in.')
            return redirect(url_for('login_or_signup'))

    return render_template('login.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    profiles = load_data(PROFILES_FILE)

    if request.method == 'POST':
        parent_age = request.form.get('parent_age')
        child_age = request.form.get('child_age')
        gender = request.form.get('gender')
        diagnosis = request.form.get('diagnosis')
        region = request.form.get('region')

        profile = next((profile for profile in profiles if profile['user_id'] == current_user.id), None)

        if profile:
            profile.update({
                'parent_age': parent_age,
                'child_age': child_age,
                'gender': gender,
                'diagnosis': diagnosis,
                'region': region
            })
        else:
            profiles.append({
                'user_id': current_user.id,
                'parent_age': parent_age,
                'child_age': child_age,
                'gender': gender,
                'diagnosis': diagnosis,
                'region': region
            })

        save_data(PROFILES_FILE, profiles)
        flash('Profile updated successfully!')
        return redirect(url_for('profile'))

    else:
        profile = next((profile for profile in profiles if profile['user_id'] == current_user.id), None)
        return render_template('profile.html', user=current_user, profile=profile)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/match', methods=['GET', 'POST'])
@login_required
def match():
    profiles = load_data(PROFILES_FILE)
    matches = []

    if request.method == 'POST':
        child_age = request.form['child_age']
        diagnosis = request.form['diagnosis']
        region = request.form['region']

        matches = [{
            'id': profile['user_id'],
            'username': next((user['username'] for user in load_data(USERS_FILE) if user['id'] == profile['user_id']), None),
            'child_age': profile['child_age'],
            'diagnosis': profile['diagnosis']
        } for profile in profiles if profile['child_age'] == child_age and profile['diagnosis'] == diagnosis and profile['region'] == region]

    return render_template('match.html', matches=matches)

@app.route('/mentor')
@login_required
def mentor():
    return render_template('mentor.html')

@app.route('/chatbot')
@login_required
def chatbot():
    return render_template('chatbot.html')

@app.route('/mentorconnection')
@login_required
def mentconnect():
    return render_template('mentorconnection.html')

@app.route('/api/mentors')
@login_required
def get_mentors():
    return send_from_directory('static/data', 'mentors.json')

@app.route('/chat/<int:match_id>')
@login_required
def chat(match_id):
    users = load_data(USERS_FILE)
    match = next((user for user in users if user['id'] == match_id), None)

    if not match:
        flash("Matched user not found.")
        return redirect(url_for('match'))

    chat_room_id = f"{min(current_user.id, match_id)}_{max(current_user.id, match_id)}"
    chat_history = load_chat_history(chat_room_id)

    return render_template('chat.html', match=match, room_id=chat_room_id, chat_history=chat_history)


def load_chat_history(chat_room_id):
    chat_file = f"chat_{chat_room_id}.json"
    if os.path.exists(chat_file):
        with open(chat_file, 'r') as file:
            return json.load(file)
    else:
        return []


# Load posts from JSON file
def load_posts():
    with open('posts.json', 'r') as file:
        return json.load(file)

# Save posts to JSON file
def save_posts(data):
    with open('posts.json', 'w') as file:
        json.dump(data, file, indent=4)

@app.route('/submit_post', methods=['POST'])
def submit_post():
    data = request.json
    title = data.get('title')
    content = data.get('content')
    section = data.get('section')

    if not title or not content or not section:
        return jsonify({"success": False, "message": "Invalid data"}), 400

    posts = load_posts()

    new_post = {
        "title": title,
        "content": content
    }

    if section == 'accomplishments':
        posts['accomplishments'].append(new_post)
    else:
        posts['blog'].append(new_post)

    save_posts(posts)

    return jsonify({"success": True})

@app.route('/load_posts', methods=['GET'])
def load_posts_route():
    posts = load_posts()
    return jsonify(posts)

@app.route('/community')
def community_page():
    return render_template('community.html')

@app.route('/netflix')
@login_required
def netflix():
    return render_template('netflix.html')

# SocketIO event handlers

@socketio.on('send_message')
def handle_send_message_event(data):
    room = data['room']
    message = {
        'sender_id': current_user.id,
        'receiver_id': data['receiver_id'],
        'username': current_user.username,
        'message': data['message'],
        'room': room
    }

    # Save message to JSON file
    chat_room_id = f"chat_{room}.json"
    if os.path.exists(chat_room_id):
        chats = load_data(chat_room_id)
    else:
        chats = []
    chats.append(message)
    save_data(chat_room_id, chats)

    emit('receive_message', message, room=room)


@socketio.on('join_room')
def handle_join_room_event(data):
    join_room(data['room'])
    emit('join_room_announcement', data, room=data['room'])

@socketio.on('leave_room')
def handle_leave_room_event(data):
    leave_room(data['room'])
    emit('leave_room_announcement', data, room=data['room'])

# API endpoints for chat

@app.route('/api/chat/<int:receiver_id>', methods=['POST'])
@login_required
def send_message_api(receiver_id):
    try:
        data = request.get_json()
        message = data['message']

        # Implement JSON-based chat storage logic here

        return jsonify({'status': 'Message sent'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/<int:receiver_id>', methods=['GET'])
@login_required
def get_messages_api(receiver_id):
    try:
        # Retrieve chat messages from JSON-based storage

        messages = []  # Replace with actual messages

        return jsonify(messages)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API to get chat history
@app.route('/chat/history')
@login_required
def chat_history():
    chats = load_data(CHATS_FILE)
    chat_history = [chat for chat in chats if 
                    chat['sender_id'] == current_user.id or 
                    chat['receiver_id'] == current_user.id]
    return jsonify(chat_history)

@app.route('/predict', methods=['GET', 'POST'])
def predict():
    prediction = None
    if request.method == 'POST':
        try:
            # Retrieve and convert input values from form
            A1 = int(request.form['A1'])
            A2 = int(request.form['A2'])
            A3 = int(request.form['A3'])
            A4 = int(request.form['A4'])
            A5 = int(request.form['A5'])
            A6 = int(request.form['A6'])
            A7 = int(request.form['A7'])
            A8 = int(request.form['A8'])
            A9 = int(request.form['A9'])
            A10 = int(request.form['A10'])
            Age_Mons = float(request.form['Age_Mons'])
            Sex = float(request.form['Sex'])
            Ethnicity = float(request.form['Ethnicity'])
            Jaundice = float(request.form['Jaundice'])
            Family_mem_with_ASD = float(request.form['Family_mem_with_ASD'])
            Who_completed_the_test = float(request.form['Who_completed_the_test'])

            # Prepare input data for prediction
            input_data = np.array([[A1, A2, A3, A4, A5, A6, A7, A8, A9, A10, Age_Mons, Sex, Ethnicity, Jaundice, Family_mem_with_ASD, Who_completed_the_test]])
            
            # Make prediction
            prediction = model.predict(input_data)[0]
        except Exception as e:
            print(f"Error: {e}")
            prediction = "Error in prediction. Please check the input values."

    return render_template('test.html', prediction=prediction)

def get_answer_from_openai(question):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question}
        ]
    )
    return response['choices'][0]['message']['content']

@app.route('/welcome_message')
def welcome_message():
    return jsonify({
        "messages": [
            {
                "english": "Welcome to Autism Assist. This chatbot supports both Arabic and English and is dedicated to assisting individuals with autism.",
                "arabic": "مرحبًا بك في مساعد التوحد. هذه الدردشة تدعم كل من العربية والإنجليزية وتهدف إلى مساعدة الأفراد المصابين بالتوحد."
            },
            {
                "english": "Feel free to ask any questions. We are here to help!",
                "arabic": "لا تتردد في طرح أي أسئلة. نحن هنا للمساعدة!"
            }
        ]
    })

def get_answer(question):
    for qa in qa_data:
        if qa['Question'].lower() == question.lower():
            return qa['Answer']
    return get_answer_from_openai(question)

@socketio.on('message')
def handle_message(data):
    question = data['question']
    answer = get_answer(question)
    emit('response', {'answer': answer})

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')  


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/mychats')
@login_required
def my_chats():
    chat_partners = {}
    user_id_pattern = re.compile(r"(\d+)_(\d+).json")

    # Get all chat files that involve the current user
    chat_files = glob.glob(f"chat_{current_user.id}_*.json") + glob.glob(f"chat_*_{current_user.id}.json")

    for chat_file in chat_files:
        match = user_id_pattern.search(chat_file)
        if match:
            user1, user2 = int(match.group(1)), int(match.group(2))
            partner_id = user2 if user1 == current_user.id else user1

            partner_username = next(
                (user['username'] for user in load_data(USERS_FILE) if user['id'] == partner_id), None)
            
            if partner_username:
                if partner_id not in chat_partners:
                    chat_partners[partner_id] = partner_username

    print(chat_partners)  # Debugging output
    return render_template('mychats.html', chat_partners=chat_partners)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=8080)
