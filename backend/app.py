import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify, g
from flask_cors import CORS

app = Flask(__name__)
# Crucial for Vercel <-> Render communication
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- CONFIGURATION ---
# In Render's Dashboard, set an Environment Variable named DATABASE_URL
DATABASE_URL = os.getenv('DATABASE_URL')


def get_db():
    """Connects to the cloud PostgreSQL database."""
    if 'db' not in g:
        # Postgres connection requires sslmode for cloud services like Neon/Supabase
        g.db = psycopg2.connect(DATABASE_URL, sslmode='require')
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Initializes the Postgres tables with correct serial types."""
    db = get_db()
    cur = db.cursor()
    # Postgres uses SERIAL for autoincrement instead of AUTOINCREMENT
    cur.execute('''
                CREATE TABLE IF NOT EXISTS chat_messages
                (
                    id         SERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role       TEXT CHECK (role IN ('user', 'assistant')),
                    content    TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                ''')
    # Add index if it doesn't exist
    cur.execute('CREATE INDEX IF NOT EXISTS idx_session ON chat_messages(session_id);')
    db.commit()
    cur.close()


# --- SMART FALLBACK LOGIC ---

def get_fallback_response(user_input):
    text = user_input.lower()

    # AI & Computer Vision
    if any(word in text for word in ["eye", "guard", "vision", "cv", "ai"]):
        return ("EyeGuard AI is one of my standout projects. It uses OpenCV for "
                "real-time eye state detection to help prevent driver fatigue.")

    # Telegram Bot Framework (The new project you added!)
    if "framework" in text or ("telegram" in text and "bot" in text and "general" in text):
        return ("I've developed a core Telegram Bot Framework on GitHub that serves as a modular "
                "foundation for building scalable, command-driven automations.")

    # Other Telegram Bots
    if any(word in text for word in ["bot", "telegram", "shop", "food"]):
        return ("I'm an expert in aiogram. My bots include a Multilingual Food Ordering bot, "
                "a Texnomart Shop bot, and a specialized Clash utility bot.")

    # Scraping & Data
    if any(word in text for word in ["scraper", "scraping", "texno", "data"]):
        return ("The Texno Scraper project demonstrates high-performance web scraping "
                "using BeautifulSoup to extract tech product data efficiently.")

    # General Skills
    if "skills" in text or "tech" in text:
        return ("Technical Stack: Python, PostgreSQL, OpenCV (AI), aiogram (Bots), "
                "Next.js, and Backend Architecture.")

    # Default
    return ("I'm ExoBot! I can tell you about EyeGuard AI, my Telegram Bot Framework, "
            "or my web scraping tools. What interests you?")


# --- ROUTES ---

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "online", "database": "postgresql"}), 200


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(force=True)
    user_message = data.get('message', '').strip()
    session_id = data.get('session_id', 'anonymous')

    if not user_message:
        return jsonify({'error': 'Message is empty'}), 400

    db = get_db()
    cur = db.cursor()

    # Postgres uses %s instead of ? for placeholders
    # 1. Save User Message
    cur.execute(
        'INSERT INTO chat_messages (session_id, role, content) VALUES (%s, %s, %s)',
        (session_id, 'user', user_message)
    )

    # 2. Process Smart Response
    bot_response = get_fallback_response(user_message)

    # 3. Save Bot Response
    cur.execute(
        'INSERT INTO chat_messages (session_id, role, content) VALUES (%s, %s, %s)',
        (session_id, 'assistant', bot_response)
    )

    db.commit()
    cur.close()

    return jsonify({
        'response': bot_response,
        'session_id': session_id
    })


@app.route('/api/messages/<session_id>', methods=['GET'])
def get_history(session_id):
    db = get_db()
    # RealDictCursor makes the result look like a dictionary {column: value}
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        'SELECT role, content, created_at FROM chat_messages WHERE session_id = %s ORDER BY created_at ASC',
        (session_id,)
    )
    messages = cur.fetchall()
    cur.close()
    return jsonify(messages)


if __name__ == '__main__':
    with app.app_context():
        init_db()

    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)