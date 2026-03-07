from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import uuid
import hashlib
from collections import defaultdict
from datetime import datetime
import json
import base64

app = Flask(__name__)
CORS(app)

users = {}
messages = defaultdict(list)
sessions = {}
last_active = {}
user_keys = {}  
pending_keys = {}  

def hash_password(password):
    return hashlib.sha3_256(password.encode()).hexdigest()

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    public_key = data.get('public_key')
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    if username in users:
        return jsonify({"error": "User already exists"}), 400
    
    users[username] = {
        "password": hash_password(password),
        "created_at": time.time(),
        "last_seen": time.time(),
        "public_key": public_key
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
        "username": username,
        "public_key": user.get("public_key")
    }), 200

@app.route('/key/exchange', methods=['POST'])
def exchange_key():
    data = request.json
    token = data.get('token')
    target_user = data.get('target_user')
    encrypted_key = data.get('encrypted_key')
    
    if token not in sessions:
        return jsonify({"error": "Invalid token"}), 401
    
    sender = sessions[token]["username"]
    
    if target_user not in users:
        return jsonify({"error": "User not found"}), 404
    
    if target_user not in pending_keys:
        pending_keys[target_user] = []
    
    pending_keys[target_user].append({
        "from": sender,
        "encrypted_key": encrypted_key,
        "time": time.time(),
        "id": str(uuid.uuid4())
    })
    
    return jsonify({"status": "key_sent"}), 200

@app.route('/key/receive', methods=['GET'])
def receive_key():
    token = request.args.get('token')
    
    if token not in sessions:
        return jsonify({"error": "Invalid token"}), 401
    
    username = sessions[token]["username"]
    
    keys = pending_keys.get(username, [])
    pending_keys[username] = []
    
    return jsonify({"keys": keys}), 200

@app.route('/key/get/<username>', methods=['GET'])
def get_public_key(username):
    token = request.args.get('token')
    
    if token not in sessions:
        return jsonify({"error": "Invalid token"}), 401
    
    user = users.get(username)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    return jsonify({
        "username": username,
        "public_key": user.get("public_key")
    }), 200

@app.route('/send', methods=['POST'])
def send_message():
    data = request.json
    token = data.get('token')
    recipient = data.get('recipient')
    encrypted_text = data.get('encrypted_text')
    key_id = data.get('key_id')
    
    if token not in sessions:
        return jsonify({"error": "Invalid token"}), 401
    
    sender = sessions[token]["username"]
    
    if recipient not in users:
        return jsonify({"error": "Recipient not found"}), 404
    
    message = {
        "from": sender,
        "encrypted_text": encrypted_text,
        "key_id": key_id,
        "time": time.time(),
        "id": str(uuid.uuid4())
    }
    
    messages[recipient].append(message)
    last_active[sender] = time.time()
    users[sender]["last_seen"] = time.time()
    
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

@app.route('/online_users', methods=['GET'])
def get_online_users():
    token = request.args.get('token')
    
    if token not in sessions:
        return jsonify({"error": "Invalid token"}), 401
    
    current_user = sessions[token]["username"]
    now = time.time()
    users_list = []
    
    for username, user_data in users.items():
        if username == current_user:
            continue
        
        last_seen = user_data.get("last_seen", 0)
        is_online = now - last_seen < 60
        
        users_list.append({
            "username": username,
            "online": is_online,
            "last_seen": last_seen,
            "has_public_key": bool(user_data.get("public_key"))
        })
    
    return jsonify({"users": users_list}), 200

@app.route('/')
def index():
    return "Secure Messenger Running"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
