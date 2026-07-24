from flask import Flask, request, render_template_string
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

# Sundar Chat Interface (Browser par chat karne ke liye)
CHAT_PAGE_HTML = """
<!DOCTYPE html>
<html lang="hi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Chat Bot</title>
    <style>
        body { font-family: Arial, sans-serif; background: #efeae2; margin: 0; padding: 20px; display: flex; justify-content: center; }
        .chat-container { width: 100%; max-width: 600px; background: #fff; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); display: flex; flex-direction: column; height: 85vh; }
        .chat-header { background: #00a884; color: white; padding: 15px; font-size: 18px; font-weight: bold; border-top-left-radius: 8px; border-top-right-radius: 8px; }
        .chat-box { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; background: #f0f2f5; }
        .message { padding: 10px 15px; border-radius: 7.5px; max-width: 75%; word-wrap: break-word; font-size: 14px; }
        .user-message { background: #d9fdd3; align-self: flex-end; }
        .ai-message { background: #ffffff; align-self: flex-start; }
        .chat-input-area { display: flex; padding: 10px; background: #f0f2f5; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; }
        .chat-input-area input { flex: 1; padding: 10px; border: 1px solid #ccc; border-radius: 20px; outline: none; font-size: 14px; }
        .chat-input-area button { background: #00a884; color: white; border: none; padding: 10px 20px; margin-left: 8px; border-radius: 20px; cursor: pointer; font-weight: bold; }
        .chat-input-area button:hover { background: #008f6f; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">🤖 Gemini AI Live Chat Box</div>
        <div class="chat-box" id="chatBox">
            <div class="message ai-message">Namaste! Main aapka AI assistant hoon. Yahan kuch bhi type karke test kar sakte hain.</div>
        </div>
        <div class="chat-input-area">
            <input type="text" id="userInput" placeholder="Yahan message type karein..." onkeypress="handleKey(event)">
            <button onclick="sendMessage()">Bhejein</button>
        </div>
    </div>

    <script>
        async function sendMessage() {
            const input = document.getElementById('userInput');
            const chatBox = document.getElementById('chatBox');
            const text = input.value.trim();
            if (!text) return;

            // User message add karein
            chatBox.innerHTML += `<div class="message user-message">${text}</div>`;
            input.value = '';
            chatBox.scrollTop = chatBox.scrollHeight;

            // Loading message
            const loadingId = 'load_' + Date.now();
            chatBox.innerHTML += `<div class="message ai-message" id="${loadingId}">Soch raha hoon...</div>`;
            chatBox.scrollTop = chatBox.scrollHeight;

            try {
                const response = await fetch('/chat-api', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text })
                });
                const data = await response.json();
                document.getElementById(loadingId).innerText = data.reply;
            } catch (err) {
                document.getElementById(loadingId).innerText = "Error: Kuch galat ho gaya.";
            }
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function handleKey(e) {
            if (e.key === 'Enter') sendMessage();
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(CHAT_PAGE_HTML)

# Browser chat ke liye API endpoint
@app.route('/chat-api', methods=['POST'])
def chat_api():
    data = request.json
    msg_body = data.get('message', '')
    reply_text = "Maaf kijiye, response generate nahi ho paya."
    
    if client and msg_body:
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=msg_body
            )
            if response and response.text:
                reply_text = response.text
        except Exception as e:
            reply_text = f"AI Error: {str(e)}"
            
    return {"reply": reply_text}

# WhatsApp Webhook route (Jaisa pehle tha)
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
        return 'Webhook active', 200

    elif request.method == 'POST':
        data = request.json
        print("Incoming WhatsApp data:", data)
        try:
            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    if 'messages' in value:
                        messages = value['messages']
                        if messages and len(messages) > 0:
                            message = messages[0]
                            from_number = message.get('from')
                            msg_body = ""
                            if 'text' in message:
                                msg_body = message['text'].get('body', '')
                            
                            if msg_body and from_number:
                                reply_text = "Maaf kijiye, response nahi mila."
                                if client:
                                    response = client.models.generate_content(
                                        model='gemini-2.0-flash',
                                        contents=msg_body
                                    )
                                    if response and response.text:
                                        reply_text = response.text
                                
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
                                requests.post(url, json=payload, headers=headers)
        except Exception as e:
            print("Webhook error:", e)
        return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)

