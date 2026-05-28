"""Test file: Intentional Python bugs for GuardianAI verification"""
import os
import subprocess
import sqlite3

# Bug 1: SQL Injection
def get_user(username):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE name = '{username}'"  # SQL injection!
    cursor.execute(query)
    return cursor.fetchone()

# Bug 2: Command injection 
def list_files(directory):
    result = os.system(f"ls {directory}")  # Unsanitized input to shell
    return result

# Bug 3: Hardcoded credentials
DATABASE_PASSWORD = "super_secret_p@ssw0rd!"
API_KEY = "sk-live-abcdefghijklmnop1234567890"

def connect():
    return sqlite3.connect(f"user:{DATABASE_PASSWORD}@db.example.com/prod")

# Bug 4: Missing null/None check
def process_result(data):
    # data might be None
    return data.strip().upper()  # AttributeError if data is None

# Bug 5: Resource leak
def read_large_file(path):
    f = open(path, 'r')
    content = f.read()
    if len(content) > 1000000:
        return None  # Leak: file not closed
    f.close()
    return content

# Bug 6: Path traversal
def serve_file(filename):
    base_dir = "/var/www/static/"
    filepath = base_dir + filename  # No sanitization against ../
    with open(filepath, 'r') as f:
        return f.read()

# Bug 7: Unreachable code
def validate(x):
    if x > 0:
        return True
    elif x <= 0:
        return False
    return None  # Dead code

# Bug 8: Subprocess with shell=True
def run_tool(user_arg):
    result = subprocess.run(f"tool --input {user_arg}", shell=True, capture_output=True)
    return result.stdout
