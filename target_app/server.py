from flask import Flask, request, jsonify, send_file
import os
import sqlite3
import subprocess
import pickle
import base64

app = Flask(__name__)

# Basic in-memory DB setup for SQLi
conn = sqlite3.connect(':memory:', check_same_thread=False)
conn.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)')
conn.execute("INSERT INTO users (username, password) VALUES ('admin', 'supersecret')")
conn.execute("INSERT INTO users (username, password) VALUES ('user', 'password')")
conn.commit()


@app.route('/download', methods=['GET'])
def download():
    """Path Traversal Vulnerability"""
    filename = request.args.get('file')
    if not filename:
        return "Missing file parameter", 400
    
    # VULNERABILITY: Unsafe concatenation of paths
    filepath = os.path.join("uploads", filename)
    try:
        return send_file(filepath)
    except FileNotFoundError:
        return "File not found", 404

@app.route('/login', methods=['POST'])
def login():
    """SQL Injection Vulnerability"""
    username = request.form.get('username')
    password = request.form.get('password')
    
    if not username or not password:
        return "Missing credentials", 400
    
    # VULNERABILITY: String formatting in SQL query
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    cursor = conn.cursor()
    cursor.execute(query)
    user = cursor.fetchone()
    
    if user:
        return jsonify({"success": True, "message": "Logged in successfully", "user_id": user[0]})
    return jsonify({"success": False, "message": "Invalid credentials"}), 401

@app.route('/ping', methods=['GET'])
def ping():
    """Command Injection Vulnerability"""
    host = request.args.get('host')
    if not host:
        return "Missing host parameter", 400
    
    # VULNERABILITY: User input directly passed to shell=True
    cmd = f"ping -c 1 {host}"
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        return f"<pre>{result.stdout}</pre>"
    except Exception as e:
        return str(e), 500

@app.route('/load_session', methods=['POST'])
def load_session():
    """Insecure Deserialization Vulnerability"""
    data = request.form.get('session_data')
    if not data:
        return "Missing session_data parameter", 400
    
    try:
        # VULNERABILITY: Unsafe pickle loading
        decoded = base64.b64decode(data)
        session_obj = pickle.loads(decoded)
        return jsonify({"status": "loaded", "data": str(session_obj)})
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    # Ensure uploads dir exists for the path traversal test
    os.makedirs("uploads", exist_ok=True)
    with open("uploads/test.txt", "w") as f:
        f.write("This is a safe file.")
        
    app.run(host='0.0.0.0', port=5000)
