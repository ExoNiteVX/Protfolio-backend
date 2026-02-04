import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify, g
from flask_cors import CORS

app = Flask(__name__)

# --- 1. ROBUST CORS CONFIG ---
# This allows your Vercel frontend to communicate freely with this backend.
CORS(app, resources={r"/api/*": {"origins": "*"}})

DATABASE_URL = os.getenv('DATABASE_URL')

def get_db():
    """Connects to Postgres and ensures the connection is still alive."""
    if 'db' not in g or g.db.closed:
        # sslmode='require' is mandatory for most cloud Postgres providers
        g.db = psycopg2.connect(DATABASE_URL, sslmode='require')
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Creates tables. Called automatically on startup."""
    db = get_db()
    cur = db.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id         SERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            role       TEXT CHECK (role IN ('user', 'assistant')),
            content    TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_session ON chat_messages(session_id);')
    db.commit()
    cur.close()

# --- 2. AUTOMATIC INITIALIZATION ---
# This runs when Gunicorn loads the app on Render.
with app.app_context():
    try:
        init_db()
        print("✅ Database initialized successfully.")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")

# --- LOGIC ---
def get_fallback_response(user_input):
    text = user_input.lower()
    if any(word in text for word in ["eye", "guard", "vision", "cv", "ai"]):
        return "EyeGuard AI uses OpenCV for real-time eye state detection to prevent driver fatigue."
    if "framework" in text or ("telegram" in text and "bot"):
        return "I've developed a modular Telegram Bot Framework on GitHub for scalable automations."
    if "skills" in text or "tech" in text:
        return "Technical Stack: Python, PostgreSQL, OpenCV, aiogram, and Next.js."
    return "I'm ExoBot! I can tell you about EyeGuard AI or my Telegram Frameworks. What's on your mind?"

# --- ROUTES ---

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "online", "database": "connected"}), 200

@app.route('/api/chat', methods=['POST'])
def chat():
    # force=True handles cases where Content-Type header might be messy
    data = request.get_json(force=True)
    user_message = data.get('message', '').strip()
    session_id = data.get('session_id', 'anonymous')

    if not user_message:
        return jsonify({'error': 'Message is empty'}), 400

    try:
        db = get_db()
        cur = db.cursor()
        
        # Save User Message
        cur.execute(
            'INSERT INTO chat_messages (session_id, role, content) VALUES (%s, %s, %s)',
            (session_id, 'user', user_message)
        )

        bot_response = get_fallback_response(user_message)

        # Save Bot Response
        cur.execute(
            'INSERT INTO chat_messages (session_id, role, content) VALUES (%s, %s, %s)',
            (session_id, 'assistant', bot_response)
        )

        db.commit()
        cur.close()

        return jsonify({'response': bot_response, 'session_id': session_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/messages/<session_id>', methods=['GET'])
def get_history(session_id):
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        'SELECT role, content, created_at FROM chat_messages WHERE session_id = %s ORDER BY created_at ASC',
        (session_id,)
    )
    messages = cur.fetchall()
    cur.close()
    return jsonify(messages)

if __name__ == '__main__':
    # For local testing only
    app.run(host='0.0.0.0', port=5000)
