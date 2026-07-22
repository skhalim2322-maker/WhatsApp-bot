import os
from flask import Flask, request, jsonify
from google import genai
import requests

app = Flask(__name__)

# Environment variables se credentials lena
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = "12345"

# Naye Google GenAI SDK ka client initialize karna
client = genai.Client(api_key=GEMINI_API_KEY)

@app.route("/", methods=["GET"])
def home():
    return "Your service is live 🚀"

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        else:
            return "Verification failed", 403
    return "Hello world", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    try:
        if data and "entry" in data:
            for entry in data["entry"]:
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    if "messages" in value:
                        messages = value["messages"]
                        for msg in messages:
                            from_number = msg["from"]
                            msg_body = msg.get("text", {}).get("body", "")
                            
                            if msg_body:
                                # Gemini AI se response generate karna (gemini-2.5-flash model ka use karke)
                                response = client.models.generate_content(
                                    model="gemini-2.5-flash",
                                    contents=msg_body
                                )
                                reply_text = response.text
                                
                                # WhatsApp par reply bhejna
                                url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
                                headers = {
                                    "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                                    "Content-Type": "application/json"
                                }
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": from_number,
                                    "type": "text",
                                    # Yahan dict ke andar "body" likhna zaroori hai
                                    "text": {"body": reply_text}
                                }
                                requests.post(url, json=headers and payload or payload, headers=headers)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
