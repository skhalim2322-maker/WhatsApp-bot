

import os
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# Firebase initialization
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
    except Exception:
        pass

db = firestore.client() if firebase_admin._apps else None

@app.route("/", methods=["GET"])
def home():
    return "WhatsApp Bot is Active and Running!", 200

# Webhook verification for Meta WhatsApp Cloud API
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    verify_token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    if verify_token == "12345":
        return challenge, 200
    return "Verification failed", 403

# Incoming messages handler from WhatsApp
@app.route("/webhook", methods=["POST"])
def handle_webhook():
    data = request.json
    try:
        if "entry" in data:
            for entry in data["entry"]:
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    if "messages" in value:
                        phone_number_id = value["metadata"]["phone_number_id"]
                        message = value["messages"][0]
                        from_number = message["from"]
                        msg_body = message["text"]["body"]
                        
                        if db:
                            db.collection("leads").add({
                                "phone_number_id": phone_number_id,
                                "from_number": from_number,
                                "message": msg_body,
                                "timestamp": firestore.SERVER_TIMESTAMP
                            })
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))



