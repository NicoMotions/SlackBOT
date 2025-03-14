import os
import slack_sdk
from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import sqlite3
import openai

# Load environment variables
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

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
                        question TEXT,
                        answer TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Store new information
def store_data(question, answer):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO knowledge (question, answer) VALUES (?, ?)", (question, answer))
    conn.commit()
    conn.close()

# Retrieve stored information
def get_answer(question):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT answer FROM knowledge WHERE question LIKE ?", ('%' + question + '%',))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# Generate AI response if no stored answer is found
def generate_ai_response(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "You are a helpful assistant."},
              {"role": "user", "content": prompt}]
    )
    return response["choices"][0]["message"]["content"].strip()

# Get the bot's user ID
def get_bot_user_id():
    response = client.auth_test()
    return response["user_id"]

# Process Slack events
@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.json
    
    # Debugging: Print the received data
    print("Received data:", data)
    
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})
    
    if "event" in data:
        event = data["event"]
        
        # Debugging: Print the event data
        print("Event data:", event)
        
        if event.get("type") == "message" and "bot_id" not in event:
            user_question = event.get("text", "").strip()
            channel = event.get("channel")
            
            # Debugging: Print the user question and channel
            print(f"User question: {user_question}, Channel: {channel}")
            
            # Check if the bot is tagged using the bot's user ID
            bot_user_id = get_bot_user_id()  # Get the bot's user ID
            
            # Check if the message mentions the bot
            if f"<@{bot_user_id}>" in user_question:
                # If the bot is tagged, check for an answer in the database
                stored_answer = get_answer(user_question)
                
                if stored_answer:
                    response_text = stored_answer
                else:
                    # If no stored answer is found, generate a new AI response
                    response_text = generate_ai_response(user_question)
                    # Store the new question-answer pair
                    store_data(user_question, response_text)
                
                # Debugging: Print the response text before sending it
                print("Response text:", response_text)
                
                try:
                    client.chat_postMessage(channel=channel, text=response_text)
                except SlackApiError as e:
                    print(f"Error sending message: {e.response['error']}")
    
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
