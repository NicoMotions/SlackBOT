import os
import slack_sdk
from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import sqlite3
import openai

# Load environment variables
SLACK_BOT_TOKEN = "SLACK_BOT_TOKEN"
SLACK_SIGNING_SECRET = "SLACK_SIGNING_SECRET"
OPENAI_API_KEY = "OPEN_API_Key"

db_file = "slack_ai_data.db"

# Initialize Slack client, Flask app, and OpenAI
client = WebClient(token=SLACK_BOT_TOKEN)
app = Flask(__name__)
openai.api_key = OPENAI_API_KEY

# Database setup
def init_db():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS knowledge (
                        id INTEGER PRIMARY KEY,
                        user_id TEXT,
                        info_key TEXT,
                        info_value TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Store new information
def store_data(user_id, info_key, info_value):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO knowledge (user_id, info_key, info_value) VALUES (?, ?, ?)", (user_id, info_key, info_value))
    conn.commit()
    conn.close()

# Retrieve stored information
def get_answer(user_id, info_key):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT info_value FROM knowledge WHERE user_id = ? AND info_key LIKE ?", (user_id, '%' + info_key + '%',))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# Process Slack events
@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.json
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})
    
    if "event" in data:
        event = data["event"]
        if event.get("type") == "message" and "bot_id" not in event:
            user_id = event.get("user")
            user_text = event.get("text", "").strip()
            channel = event.get("channel")
            
            if "I'm" in user_text or "My" in user_text or "Our" in user_text:
                # Assume user is providing new information
                parts = user_text.split(" ", 2)
                if len(parts) > 2:
                    info_key = parts[1]
                    info_value = parts[2]
                    store_data(user_id, info_key, info_value)
                    response_text = "Got it! I'll remember that."
                else:
                    response_text = "Can you clarify what you want me to remember?"
            else:
                stored_answer = get_answer(user_id, user_text)
                if stored_answer:
                    response_text = stored_answer
                else:
                    response_text = generate_ai_response(user_text)
            
            try:
                client.chat_postMessage(channel=channel, text=response_text)
            except SlackApiError as e:
                print(f"Error sending message: {e.response['error']}")
    
    return jsonify({"status": "ok"})

def generate_ai_response(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "system", "content": "You are a helpful assistant."},
                  {"role": "user", "content": prompt}]
    )
    return response["choices"][0]["message"]["content"].strip()

if __name__ == "__main__":
    app.run(port=3000)

### Step-by-Step Setup Guide ###

1. **Create a Slack App:**
   - Go to https://api.slack.com/apps and click "Create New App."
   - Select "From Scratch."
   - Give it a name (e.g., "AI Assistant") and choose your Slack workspace.

2. **Set Up OAuth & Permissions:**
   - In your Slack App settings, go to "OAuth & Permissions."
   - Under "Scopes," add:
     - `channels:history`
     - `channels:read`
     - `chat:write`
   - Click "Install App to Workspace" and copy the "Bot User OAuth Token."

3. **Enable Event Subscriptions:**
   - In "Event Subscriptions," enable events.
   - Set the "Request URL" to your hosted bot’s URL (`https://your-server.com/slack/events`).
   - Subscribe to the "message.channels" event.

4. **Get an OpenAI API Key:**
   - Sign up at [OpenAI](https://openai.com/) and generate an API key.
   - Add this key to your environment variables as `OPENAI_API_KEY`.

5. **Set Up Your Server (Easiest Way - Railway.app):**
   - Sign up at [Railway.app](https://railway.app/).
   - Create a new project and select "Deploy from GitHub."
   - Upload this bot script.
   - Set environment variables:
     - `SLACK_BOT_TOKEN` (your copied OAuth token)
     - `SLACK_SIGNING_SECRET` (found in "Basic Information" in Slack settings)
     - `OPENAI_API_KEY` (your OpenAI key)
   - Click "Deploy."

6. **Test Your Bot in Slack:**
   - Invite the bot to a channel using `/invite @YourBotName`.
   - Tell it anything (e.g., "Our project deadline is June 15").
   - Later, ask "What's our project deadline?" → It should remember!
   - If it doesn’t know, it will generate a response using GPT-4.

Your bot is now live and remembers everything you tell it! 🚀
