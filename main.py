import os
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# ==========================================
# 1. FIREBASE DATABASE SETUP
# ==========================================
# (Dhyan rahe: Aapko Firebase se JSON file download karke 'firebase-key.json' 
# naam se apne GitHub me upload karni hogi, tabhi database connect hoga)
try:
    if os.path.exists("firebase-key.json"):
        cred = credentials.Certificate("firebase-key.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase Database Connected Successfully!")
    else:
        print("⚠️ WARNING: 'firebase-key.json' file nahi mili! App chalega, par data save nahi hoga.")
        db = None
except Exception as e:
    print("❌ Firebase Connection Error:", e)
    db = None

# ==========================================
# 2. META WEBHOOK VERIFICATION
# ==========================================
VERIFY_TOKEN = "12345"

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("✅ Webhook Verified by Meta!")
            return challenge, 200
        else:
            return "Verification failed", 403
    return "Webhook is active", 200

# ==========================================
# 3. RECEIVE MESSAGES & SAVE TO FIREBASE
# ==========================================
@app.route('/webhook', methods=['POST'])
def receive_message():
    data = request.get_json()
    print("📩 New Data Received:", data)

    try:
        if data.get('object') == 'whatsapp_business_account':
            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    
                    if 'messages' in value:
                        for message in value['messages']:
                            sender_phone = message.get('from')
                            msg_text = message.get('text', {}).get('body', '')
                            msg_id = message.get('id')
                            timestamp = message.get('timestamp')

                            print(f"Message from {sender_phone}: {msg_text}")

                            # Firebase Database me Data Save karna
                            if db is not None:
                                doc_ref = db.collection('client_messages').document(msg_id)
                                doc_ref.set({
                                    'phone_number': sender_phone,
                                    'message_text': msg_text,
                                    'timestamp': timestamp,
                                    'status': 'received'
                                })
                                print("✅ Message Firebase DataBase me Save ho gaya!")
                            else:
                                print("⚠️ Firebase key nahi hai, data save skip kiya gaya.")
                                
    except Exception as e:
        print("❌ Error processing message:", e)

    return jsonify({"status": "success"}), 200

# ==========================================
# 4. HOME PAGE (App check karne ke liye)
# ==========================================
@app.route('/', methods=['GET'])
def home():
    return "<h1>WhatsApp App Backend with Firebase is 100% Active!</h1>", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
