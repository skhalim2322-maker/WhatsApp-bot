from flask import Flask, request
import os
import requests
from google import genai

app = Flask(__name__)

# Gemini Client setup
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

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
            entry = data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']
            
            if 'messages' in value:
                message = value['messages'][0]
                from_number = message['from']
                
                # Check if message is text or audio
                msg_body = ""
                if 'text' in message:
                    msg_body = message['text']['body']
                elif 'audio' in message:
                    msg_body = "User ne voice message bheja hai. (Abhi text mein jawab de raha hoon)."
                
                if msg_body:
                    print(f"Message received from {from_number}: {msg_body}")
                    
                    # Gemini AI se response generate karna
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=msg_body
                    )
                    reply_text = response.text
                    
                    # WhatsApp par text message bhejna
                    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
                    headers = {
                        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "messaging_product": "whatsapp",
                        "to": from_number,
                        "text": {"body": reply_text}
                    }
                    requests.post(url, json=payload, headers=headers)
                
        except Exception as e:
            print("Error processing message:", e)
            
        return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
