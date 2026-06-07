import os
import sqlite3
import subprocess
import pickle
import yaml
from flask import Flask, request, render_template_string, jsonify

app = Flask(__name__)

# Hardcoded Secret (MEDIUM)
SECRET_KEY = "my_super_secret_key_12345"
app.secret_key = SECRET_KEY

# In-memory DB setup
db_conn = sqlite3.connect(':memory:', check_same_thread=False)
db_conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)")
db_conn.execute("INSERT INTO users (username, password) VALUES ('admin', 'admin123')")
db_conn.commit()

@app.route('/')
def index():
    return "Welcome to the vulnerable server! Try /files?path=readme.txt or /user?username=admin"

# Path Traversal (HIGH)
@app.route('/files')
def get_file():
    filepath = request.args.get('path', 'readme.txt')
    # Vulnerable: No validation before os.path.join and open
    full_path = os.path.join('/tmp', filepath)
    try:
        with open(full_path, 'r') as f:
            return f.read()
    except Exception as e:
        return str(e), 500

# SQL Injection (CRITICAL)
@app.route('/user')
def get_user():
    username = request.args.get('username', '')
    # Vulnerable: string formatting in SQL query
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor = db_conn.cursor()
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        return jsonify(result)
    except Exception as e:
        return str(e), 500

# Command Injection (CRITICAL)
@app.route('/ping')
def ping_host():
    host = request.args.get('host', '127.0.0.1')
    # Vulnerable: shell=True with user input
    try:
        output = subprocess.check_output(f"ping -c 1 {host}", shell=True, text=True)
        return output
    except subprocess.CalledProcessError as e:
        return str(e), 500

# Insecure Deserialization (CRITICAL)
@app.route('/load_config', methods=['POST'])
def load_config():
    data = request.data
    # Vulnerable: pickle.loads on user input
    try:
        config = pickle.loads(data)
        return jsonify({"status": "loaded", "config": str(config)})
    except Exception as e:
        return str(e), 500

# XSS (HIGH)
@app.route('/hello')
def hello():
    name = request.args.get('name', 'Guest')
    # Vulnerable: rendering template string with user input
    template = f"<h1>Hello, {name}!</h1>"
    return render_template_string(template)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9999)
