from flask import Flask, request, redirect, render_template_string
import sqlite3
import uuid
import re
import os

app = Flask(__name__)
DB_FILE = "pings.db"

# --------------------------
# Database Setup
# --------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_pings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            pinged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# --------------------------
# Slug Generator
# --------------------------
def generate_slug(email):
    base = re.sub(r'[^\w]+', '', email.split('@')[0].lower())
    unique = uuid.uuid4().hex[:6]
    return f"{base}-{unique}"

# --------------------------
# Routes
# --------------------------
@app.route('/')
def home():
    return render_template_string('''
        <h2>Email Slug Generator</h2>
        <form method="POST" action="/create">
            <input type="email" name="email" required>
            <button type="submit">Generate Slug URL</button>
        </form>
    ''')

@app.route('/create', methods=['POST'])
def create_slug():
    email = request.form['email']
    slug = generate_slug(email)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO email_pings (email, slug) VALUES (?, ?)", (email, slug))
    conn.commit()
    conn.close()

    return f"Your ping URL is: <a href='/ping/{slug}'>/ping/{slug}</a>"

@app.route('/ping/<slug>')
def ping(slug):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT email, pinged_at FROM email_pings WHERE slug = ?", (slug,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return f"Ping received from <b>{row[0]}</b> at {row[1]}"
    return "Invalid or expired slug", 404

# --------------------------
# Start the App
# --------------------------
if __name__ == '__main__':
    if not os.path.exists(DB_FILE):
        init_db()
    app.run(debug=True)
