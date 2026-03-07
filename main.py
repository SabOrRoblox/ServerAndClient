from flask import Flask, request, jsonify
from flask_cors import CORS
import time
from collections import defaultdict
import threading

app = Flask(__name__)
CORS(app)

messages = defaultdict(list)
last_check = defaultdict(lambda: time.time())

@app.route('/send', methods=['POST'])
def send_message():
    data = request.json
    sender = data.get('sender')
    recipient = data.get('recipient')
    text = data.get('text')
    
    if not all([sender, recipient, text]):
        return jsonify({"error": "Missing fields"}), 400
    
    message = {
        "from": sender,
        "text": text,
        "time": time.time()
    }
    
    messages[recipient].append(message)
    print(f"[{sender} -> {recipient}]: {text}")
    
    return jsonify({"status": "sent"}), 200

@app.route('/receive/<username>', methods=['GET'])
def receive_messages(username):
    client_last_check = float(request.args.get('since', last_check[username]))
    
    new_messages = [
        msg for msg in messages[username] 
        if msg['time'] > client_last_check
    ]
    
    if new_messages:
        last_check[username] = max(msg['time'] for msg in new_messages)
    
    return jsonify({
        "messages": new_messages,
        "count": len(new_messages)
    })

@app.route('/users', methods=['GET'])
def get_users():
    active_users = set()
    for recipient in messages.keys():
        active_users.add(recipient)
    for sender in messages.keys():
        active_users.add(sender)
    
    return jsonify({"users": list(active_users)})

@app.route('/')
def index():
    return "Messenger Server is running!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
