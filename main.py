from flask import Flask, request
import os
import requests
from google import genai

app = Flask(__name__)

# Gemini API configuration
API_KEY = os.environ.get("GEMINI_API_KEY")
client = None
if API_KEY:
    try:
        client = genai.Client(api_key=API_KEY)
    except Exception as e:
        print("Gemini Client Init Error:", e)
else:
    print("WARNING: GEMINI_API_KEY is not set!")

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = "12345"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode and token:
            if mode == 'subscribe' and token == VERIFY_TOKEN:
                return challenge, 200
            else:
                return 'Verification failed', 403
        return 'Hello world', 200

    elif request.method == 'POST':
        data = request.json
        print("Incoming data:", data)
        
        try:
            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    
                    # Check if messages exist in payload
                    if 'messages' in value:
                        messages = value['messages']
                        if messages and len(messages) > 0:
                            message = messages[0]
                            from_number = message.get('from')
                            
                            msg_body = ""
                            if 'text' in message:
                                msg_body = message['text'].get('body', '')
                            elif 'audio' in message:
                                msg_body = "User sent an audio message."
                            
                            if msg_body and from_number:
                                print(f"Message received from {from_number}: {msg_body}")
                                
                                # Gemini AI response generation
                                reply_text = "Sorry, I am unable to generate a response right now."
                                if client:
                                    try:
                                        response = client.models.generate_content(
                                            model='gemini-2.0-flash',
                                            contents=msg_body
                                        )
                                        if response and response.text:
                                            reply_text = response.text
                                        print(f"Gemini Response Generated: {reply_text}")
                                    except Exception as ai_err:
                                        print("Gemini API Error:", ai_err)
                                
                                # Send back to WhatsApp using v21.0
                                url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
                                headers = {
                                    "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                                    "Content-Type": "application/json"
                                }
                                payload = {
                                    "messaging_product": "whatsapp",
                                    "to": from_number,
                                    "text": {"body": reply_text}
                                }
                                
                                wa_response = requests.post(url, json=payload, headers=headers)
                                print("WhatsApp Send Response:", wa_response.status_code, wa_response.text)
                
        except Exception as e:
            print("Error processing message:", e)
            
        return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
