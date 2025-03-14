import os
import slack_sdk
import logging
from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import sqlite3
import openai

# Setup logging for better debugging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET or not OPENAI_API_KEY:
    logging.error("Missing required environment variables.")
    raise ValueError("Missing environment variables")

# Initialize Slack client, Flask app, and OpenAI
client = WebClient(token=SLACK_BOT_TOKEN)
app = Flask(__name__)
openai.api_key = OPENAI_API_KEY

# Database setup
db_file = "slack_ai_data.db"

def init_db():
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS knowledge (
                            id INTEGER PRIMARY KEY,
                            question TEXT,
                            answer TEXT)''')
        conn.commit()
        conn.close()
        logging.debug("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")
        raise

init_db()

# Store new information
def store_data(question, answer):
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO knowledge (question, answer) VALUES (?, ?)", (question, answer))
        conn.commit()
        conn.close()
        logging.debug(f"Stored new data: {question} -> {answer}")
    except Exception as e:
        logging.error(f"Error storing data: {e}")

# Retrieve stored information
def get_answer(question):
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT answer FROM knowledge WHERE question LIKE ?", ('%' + question + '%',))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logging.error(f"Error retrieving data: {e}")
        return None

# Generate AI response if no stored answer is found
def generate_ai_response(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "You are a helpful assistant."},
                      {"role": "user", "content": prompt}]
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.error(f"Error generating AI response: {e}")
        return "Sorry, I couldn't process your request."

# Process Slack events
@app.route("/slack/events", methods=["POST"])
def slack_events():
    try:
        data = request.json
        logging.debug(f"Received data: {data}")
        
        if "challenge" in data:
            return jsonify({"challenge": data["challenge"]})

        if "event" in data:
            event = data["event"]
            logging.debug(f"Received event: {event}")
            
            if event.get("type") == "message" and "bot_id" not in event:
                user_question = event.get("text", "").strip()
                channel = event.get("channel")
                
                stored_answer = get_answer(user_question)
                if stored_answer:
                    response_text = stored_answer
                else:
                    response_text = generate_ai_response(user_question)
                
                try:
                    client.chat_postMessage(channel=channel, text=response_text)
                    logging.debug(f"Message sent: {response_text}")
                except SlackApiError as e:
                    logging.error(f"Error sending message: {e.response['error']}")
        
        return jsonify({"status": "ok"})
    
    except Exception as e:
        logging.error(f"Error in /slack/events: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Simple test route
@app.route("/", methods=["GET"])
def home():
    return "App is running"

# Run Flask app (Railway assigns the port via environment variable)
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 3000)))
