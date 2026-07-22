import os
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# Firebase initialization (Modified for cloud deployment)
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

@app.route("/", methods=["GET"])
def home():
    return "WhatsApp Bot Backend is Running Securely!", 200

# Webhook verification for Meta WhatsApp Cloud API
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    verify_token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    # Aap apna custom verify token yahan set kar sakte hain
    if verify_token == "nexus_ops_secure_token":
        return challenge, 200
    return "Verification failed", 403

# Incoming messages handler from WhatsApp
@app.route("/webhook", methods=["POST"])
def handle_webhook():
    data = request.json
    try:
        # Check if message exists from WhatsApp payload
        if "entry" in data:
            for entry in data["entry"]:
                for change in entry.get("changes", []):
                    value = change.get("value", ())
                    if "messages" in value:
                        phone_number_id = value["metadata"]["phone_number_id"]
                        message = value["messages"][0]
                        from_number = message["from"]
                        msg_body = message["text"]["body"]

                        # Store lead securely in Firestore under specific broker/phone mapping
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


