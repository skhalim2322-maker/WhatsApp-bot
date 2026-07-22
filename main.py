import os
import requests
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai

app = Flask(__name__)

# ==========================================
# CONFIGURATIONS
# ==========================================
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "12345")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")  
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "") 
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")   

# Gemini AI Setup
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    system_instruction = "You are a helpful WhatsApp assistant. Always reply to the user in the exact same language (e.g., Hindi, English, Bengali, Hinglish, etc.) in which the user has messaged you."
    
    gemini_model = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        system_instruction=system_instruction
    )
else:
    gemini_model = None

# ==========================================
# 1. FIREBASE DATABASE SETUP (Crash Proof)
# ==========================================
db = None
try:
    if os.path.exists("firebase-key.json"):
        cred = credentials.Certificate("firebase-key.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase Database Connected Successfully!")
    else:
        print("⚠️ WARNING: 'firebase-key.json' file nahi mili, par server chalu rahega.")
except Exception as e:
    print("❌ Firebase Connection Error (Server crash nahi hoga):", e)

# ==========================================
# 2. META WEBHOOK VERIFICATION
# ==========================================
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
# 3. RECEIVE, PROCESS & SAFE REPLY
# ==========================================
@app.route('/webhook', methods=['POST'])
def receive_message():
    try:
        data = request.get_json()
        print("📩 New Data Received:", data)

        if data and data.get('object') == 'whatsapp_business_account':
            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    
                    if 'messages' in value:
                        for message in value['messages']:
                            sender_phone = message.get('from')
                            msg_text = message.get('text', {}).get('body', '')
                            msg_id = message.get('id', 'unknown_id')
                            timestamp = message.get('timestamp', '')

                            print(f"Message from {sender_phone}: {msg_text}")

                            # Safe Default Reply (Agar AI ya kuch bhi fail ho)
                            ai_reply = "Namaste! Aapka message mil gaya hai. Hum jaldi hi aapse sampark karenge."

                            # Gemini AI se smart reply lene ki koshish
                            if gemini_model and msg_text:
                                try:
                                    response = gemini_model.generate_content(msg_text)
                                    if response and response.text:
                                        ai_reply = response.text
                                except Exception as ai_err:
                                    print("❌ Gemini AI Error (Safe fallback use hoga):", ai_err)

                            # WhatsApp par message bhejna
                            send_whatsapp_message(sender_phone, ai_reply)

                            # Firebase mein save karna (Agar database down bhi ho toh crash nahi hoga)
                            if db is not None:
                                try:
                                    doc_ref = db.collection('client_messages').document(str(msg_id))
                                    doc_ref.set({
                                        'phone_number': sender_phone,
                                        'message_text': msg_text,
                                        'ai_reply': ai_reply,
                                        'timestamp': timestamp,
                                        'status': 'replied'
                                    })
                                    print("✅ Message Firebase mein save ho gaya!")
                                except Exception as db_err:
                                    print("⚠️ Database Save Error (Ignored to prevent crash):", db_err)
                                    
    except Exception as e:
        print("❌ Critical Error in receive_message (Server safe hai):", e)

    return jsonify({"status": "success"}), 200

def send_whatsapp_message(recipient_phone, text_message):
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("⚠️ WhatsApp Token ya Phone Number ID missing hai.")
        return
    
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "text",
        "text": {"body": text_message}
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers)
        print("📤 WhatsApp Send Response:", res.json())
    except Exception as err:
        print("❌ Error sending WhatsApp message:", err)

# ==========================================
# 4. HOME PAGE
# ==========================================
@app.route('/', methods=['GET'])
def home():
    return "<h1>WhatsApp Crash-Proof AI Bot is 100% Active!</h1>", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
