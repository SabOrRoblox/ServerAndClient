from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import uuid
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

users = {}
messages = defaultdict(list)
sessions = {}
last_active = {}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    if username in users:
        return jsonify({"error": "User already exists"}), 400
    
    users[username] = {
        "password": hash_password(password),
        "created_at": time.time(),
        "last_seen": time.time()
    }
    
    return jsonify({"status": "registered", "username": username}), 200

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    user = users.get(username)
    if not user or user["password"] != hash_password(password):
        return jsonify({"error": "Invalid credentials"}), 401
    
    token = str(uuid.uuid4())
    sessions[token] = {
        "username": username,
        "login_time": time.time()
    }
    last_active[username] = time.time()
    user["last_seen"] = time.time()
    
    return jsonify({
        "status": "logged_in",
        "token": token,
        "username": username
    }), 200

@app.route('/logout', methods=['POST'])
def logout():
    data = request.json
    token = data.get('token')
    
    if token in sessions:
        username = sessions[token]["username"]
        del sessions[token]
        if username in last_active:
            del last_active[username]
        return jsonify({"status": "logged_out"}), 200
    
    return jsonify({"error": "Invalid token"}), 400

@app.route('/online_users', methods=['GET'])
def get_online_users():
    token = request.args.get('token')
    
    if token not in sessions:
        return jsonify({"error": "Invalid token"}), 401
    
    current_user = sessions[token]["username"]
    now = time.time()
    online = []
    offline = []
    
    for username, user_data in users.items():
        if username == current_user:
            continue
        
        last_seen = user_data.get("last_seen", 0)
        if now - last_seen < 60:
            online.append({
                "username": username,
                "last_seen": "online"
            })
        else:
            offline.append({
                "username": username,
                "last_seen": datetime.fromtimestamp(last_seen).strftime('%Y-%m-%d %H:%M')
            })
    
    return jsonify({
        "online": online,
        "offline": offline
    }), 200

@app.route('/send', methods=['POST'])
def send_message():
    data = request.json
    token = data.get('token')
    recipient = data.get('recipient')
    text = data.get('text')
    
    if token not in sessions:
        return jsonify({"error": "Invalid token"}), 401
    
    sender = sessions[token]["username"]
    
    if recipient not in users:
        return jsonify({"error": "Recipient not found"}), 404
    
    message = {
        "from": sender,
        "text": text,
        "time": time.time(),
        "id": str(uuid.uuid4())
    }
    
    messages[recipient].append(message)
    last_active[sender] = time.time()
    users[sender]["last_seen"] = time.time()
    
    print(f"[{sender} -> {recipient}]: {text}")
    
    return jsonify({"status": "sent", "message_id": message["id"]}), 200

@app.route('/receive', methods=['GET'])
def receive_messages():
    token = request.args.get('token')
    since = float(request.args.get('since', 0))
    
    if token not in sessions:
        return jsonify({"error": "Invalid token"}), 401
    
    username = sessions[token]["username"]
    last_active[username] = time.time()
    users[username]["last_seen"] = time.time()
    
    new_messages = [
        msg for msg in messages[username] 
        if msg['time'] > since
    ]
    
    return jsonify({
        "messages": new_messages,
        "count": len(new_messages),
        "server_time": time.time()
    }), 200

@app.route('/users', methods=['GET'])
def get_users_list():
    token = request.args.get('token')
    
    if token not in sessions:
        return jsonify({"error": "Invalid token"}), 401
    
    return jsonify({
        "users": list(users.keys())
    }), 200

@app.route('/')
def index():
    return f"Messenger Server Running. Users: {len(users)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
