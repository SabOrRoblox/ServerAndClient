from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from supabase import create_client
import time
import uuid
import hashlib
import secrets
import hmac
from datetime import datetime, timedelta
from collections import defaultdict
import json
import os

app = Flask(__name__, static_folder='static')
CORS(app)

SUPABASE_URL = "https://kuhunkdgbtedgrujwxoy.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt1aHVua2RnYnRlZGdydWp3eG95Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTQyOTMyODEsImV4cCI6MjA2OTg2OTI4MX0.N5I9bGTroqMDD9g0b-3lqMMip0NFRDTH30dh_hQ9kJY"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

active_sessions = {}
online_users = set()
pending_keys = defaultdict(list)

def hash_password(password):
    return hashlib.sha3_256(password.encode()).hexdigest()

def generate_token():
    return secrets.token_urlsafe(32)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('static', path)

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    public_key = data.get('public_key')
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    existing = supabase.table('users').select('*').eq('username', username).execute()
    if existing.data:
        return jsonify({"error": "User already exists"}), 400
    
    user = {
        'username': username,
        'password': hash_password(password),
        'public_key': public_key,
        'created_at': time.time(),
        'last_seen': time.time()
    }
    
    supabase.table('users').insert(user).execute()
    return jsonify({"status": "registered"}), 200

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    result = supabase.table('users').select('*').eq('username', username).execute()
    if not result.data:
        return jsonify({"error": "Invalid credentials"}), 401
    
    user = result.data[0]
    if user['password'] != hash_password(password):
        return jsonify({"error": "Invalid credentials"}), 401
    
    token = generate_token()
    active_sessions[token] = {
        'username': username,
        'login_time': time.time()
    }
    online_users.add(username)
    
    supabase.table('users').update({'last_seen': time.time()}).eq('username', username).execute()
    
    return jsonify({
        "status": "logged_in",
        "token": token,
        "username": username,
        "public_key": user.get('public_key')
    }), 200

@app.route('/api/logout', methods=['POST'])
def logout():
    data = request.json
    token = data.get('token')
    
    if token in active_sessions:
        username = active_sessions[token]['username']
        online_users.discard(username)
        del active_sessions[token]
    
    return jsonify({"status": "logged_out"}), 200

@app.route('/api/key/exchange', methods=['POST'])
def key_exchange():
    data = request.json
    token = data.get('token')
    target_user = data.get('target_user')
    public_key = data.get('public_key')
    key_id = data.get('key_id')
    
    if token not in active_sessions:
        return jsonify({"error": "Invalid token"}), 401
    
    sender = active_sessions[token]['username']
    
    result = supabase.table('users').select('*').eq('username', target_user).execute()
    if not result.data:
        return jsonify({"error": "User not found"}), 404
    
    pending_keys[target_user].append({
        "from": sender,
        "public_key": public_key,
        "key_id": key_id,
        "time": time.time()
    })
    
    return jsonify({"status": "sent"}), 200

@app.route('/api/key/receive', methods=['GET'])
def key_receive():
    token = request.args.get('token')
    
    if token not in active_sessions:
        return jsonify({"error": "Invalid token"}), 401
    
    username = active_sessions[token]['username']
    keys = pending_keys.get(username, [])
    pending_keys[username] = []
    
    return jsonify({"keys": keys}), 200

@app.route('/api/key/get/<username>', methods=['GET'])
def get_public_key(username):
    token = request.args.get('token')
    
    if token not in active_sessions:
        return jsonify({"error": "Invalid token"}), 401
    
    result = supabase.table('users').select('public_key').eq('username', username).execute()
    if not result.data:
        return jsonify({"error": "User not found"}), 404
    
    return jsonify({
        "username": username,
        "public_key": result.data[0].get('public_key')
    }), 200

@app.route('/api/send', methods=['POST'])
def send_message():
    data = request.json
    token = data.get('token')
    recipient = data.get('recipient')
    encrypted_text = data.get('encrypted_text')
    key_id = data.get('key_id')
    nonce = data.get('nonce')
    msg_id = data.get('msg_id', str(uuid.uuid4()))
    
    if token not in active_sessions:
        return jsonify({"error": "Invalid token"}), 401
    
    sender = active_sessions[token]['username']
    
    result = supabase.table('users').select('*').eq('username', recipient).execute()
    if not result.data:
        return jsonify({"error": "Recipient not found"}), 404
    
    message = {
        'from': sender,
        'to': recipient,
        'encrypted_text': encrypted_text,
        'key_id': key_id,
        'nonce': nonce,
        'time': time.time(),
        'id': msg_id,
        'delivered': False
    }
    
    supabase.table('messages').insert(message).execute()
    
    return jsonify({"status": "sent", "message_id": msg_id}), 200

@app.route('/api/receive', methods=['GET'])
def receive_messages():
    token = request.args.get('token')
    since = float(request.args.get('since', 0))
    
    if token not in active_sessions:
        return jsonify({"error": "Invalid token"}), 401
    
    username = active_sessions[token]['username']
    
    supabase.table('users').update({'last_seen': time.time()}).eq('username', username).execute()
    online_users.add(username)
    
    result = supabase.table('messages')\
        .select('*')\
        .eq('to', username)\
        .gt('time', since)\
        .order('time', desc=False)\
        .execute()
    
    messages = result.data if result.data else []
    
    return jsonify({
        "messages": messages,
        "count": len(messages),
        "server_time": time.time()
    }), 200

@app.route('/api/online_users', methods=['GET'])
def get_online_users():
    token = request.args.get('token')
    
    if token not in active_sessions:
        return jsonify({"error": "Invalid token"}), 401
    
    now = time.time()
    result = supabase.table('users').select('username, last_seen').execute()
    
    users_list = []
    for user in result.data if result.data else []:
        if user['username'] == active_sessions[token]['username']:
            continue
        
        last_seen = user.get('last_seen', 0)
        is_online = user['username'] in online_users or (now - last_seen < 60)
        
        users_list.append({
            "username": user['username'],
            "online": is_online,
            "last_seen": last_seen
        })
    
    return jsonify({"users": users_list}), 200

@app.route('/api/history/<username>', methods=['GET'])
def get_history(username):
    token = request.args.get('token')
    limit = int(request.args.get('limit', 50))
    
    if token not in active_sessions:
        return jsonify({"error": "Invalid token"}), 401
    
    current_user = active_sessions[token]['username']
    
    result = supabase.table('messages')\
        .select('*')\
        .or_(
            f'and(from.eq.{current_user},to.eq.{username}),' +
            f'and(from.eq.{username},to.eq.{current_user})'
        )\
        .order('time', desc=True)\
        .limit(limit)\
        .execute()
    
    messages = result.data if result.data else []
    
    return jsonify({"messages": messages}), 200

@app.route('/api/status', methods=['POST'])
def update_status():
    data = request.json
    token = data.get('token')
    status = data.get('status')
    
    if token not in active_sessions:
        return jsonify({"error": "Invalid token"}), 401
    
    username = active_sessions[token]['username']
    
    supabase.table('users').update({'status': status}).eq('username', username).execute()
    
    return jsonify({"status": "updated"}), 200

@app.route('/api/health')
def health():
    return jsonify({
        "status": "ok",
        "time": time.time(),
        "users": len(online_users),
        "sessions": len(active_sessions)
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
