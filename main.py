



import os
from flask import Flask, request, jsonify

app = Flask(__name__)

VERIFY_TOKEN = "12345"

@app.route("/", methods=["GET"])
def home():
    return "WhatsApp Multi-User Bot is Running Successfully!"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    # Webhook Verification for Meta
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode and token:
            if mode == "subscribe" and token == VERIFY_TOKEN:
                print("WEBHOOK_VERIFIED")
                return challenge, 200
            else:
                return "Verification failed", 403
        return "Hello World", 200

    # Receiving Messages from any Client/User
    elif request.method == "POST":
        data = request.json
        print("Received Incoming Data:", data)
        
        try:
            if (
                data.get("entry")
                and data["entry"][0].get("changes")
                and data["entry"][0]["changes"][0].get("value")
                and data["entry"][0]["changes"][0]["value"].get("messages")
            ):
                phone_number_id = data["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]
                from_number = data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
                msg_body = data["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
                
                print(f"-> Bot ID: {phone_number_id} | From: {from_number} | Message: {msg_body}")
        except Exception as e:
            print(f"Error parsing incoming message: {e}")

        return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
