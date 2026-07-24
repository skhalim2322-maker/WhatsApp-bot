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

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = "12345"

# Nexus Ops Professional Dashboard HTML & CSS UI
NEXUS_OPS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nexus Ops - Command Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
        body { background-color: #f4f6f9; color: #333; display: flex; height: 100vh; overflow: hidden; }
        
        /* Sidebar */
        .sidebar { width: 260px; background-color: #0f172a; color: #94a3b8; display: flex; flex-direction: column; border-right: 1px solid #1e293b; }
        .sidebar-brand { padding: 20px; font-size: 20px; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid #1e293b; }
        .sidebar-brand i { color: #3b82f6; }
        .sidebar-menu { list-style: none; padding: 20px 10px; flex: 1; }
        .sidebar-menu li { padding: 12px 15px; margin-bottom: 5px; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 12px; font-size: 14px; font-weight: 500; transition: all 0.3s; }
        .sidebar-menu li:hover, .sidebar-menu li.active { background-color: #1e293b; color: #fff; }
        .sidebar-menu li.active { background-color: #2563eb; color: #fff; }

        /* Main Content Area */
        .main-content { flex: 1; display: flex; flex-direction: column; overflow-y: auto; }
        
        /* Header */
        .header { background: #fff; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e2e8f0; }
        .header-title { font-size: 18px; font-weight: 600; color: #1e293b; }
        .header-right { display: flex; align-items: center; gap: 20px; }
        .user-profile { display: flex; align-items: center; gap: 10px; font-weight: 500; font-size: 14px; }
        .user-profile img { width: 35px; height: 35px; border-radius: 50%; object-fit: cover; }

        /* Dashboard Body */
        .dashboard-body { padding: 30px; display: flex; flex-direction: column; gap: 25px; }

        /* Status Pills Row */
        .status-row { display: flex; gap: 15px; }
        .status-pill { background: #fff; padding: 10px 20px; border-radius: 8px; border: 1px solid #e2e8f0; font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .status-pill .dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; }

        /* Grid Section */
        .dashboard-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 25px; }
        
        /* Cards */
        .card { background: #fff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .card-title { font-size: 15px; font-weight: 600; color: #1e293b; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }

        /* KPI Cards */
        .kpi-container { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 25px; }
        .kpi-card { background: #fff; border-radius: 12px; padding: 20px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .kpi-card.blue { background: #2563eb; color: #fff; border: none; }
        .kpi-card.blue .kpi-label, .kpi-card.blue .kpi-sub { color: #dbeafe; }
        .kpi-label { font-size: 13px; color: #64748b; font-weight: 500; }
        .kpi-value { font-size: 26px; font-weight: 700; margin: 8px 0; color: #0f172a; }
        .kpi-card.blue .kpi-value { color: #fff; }
        .kpi-sub { font-size: 12px; color: #16a34a; font-weight: 600; }

        /* Lists & Tables */
        .list-item { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #f1f5f9; font-size: 13px; }
        .list-item:last-child { border-bottom: none; }
        .badge { padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }
        .badge.pending { background: #fef3c7; color: #d97706; }
        .badge.progress { background: #dbeafe; color: #1d4ed8; }
        .badge.success { background: #dcfce7; color: #15803d; }

        /* Config Toggles */
        .config-item { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #f1f5f9; font-size: 13px; font-weight: 500; }
        .switch { position: relative; display: inline-block; width: 40px; height: 22px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #cbd5e1; transition: .4s; border-radius: 22px; }
        .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }
        input:checked + .slider { background-color: #22c55e; }
        input:checked + .slider:before { transform: translateX(18px); }

        /* AI Chat Box Section inside Dashboard */
        .chat-section { margin-top: 10px; display: flex; flex-direction: column; gap: 10px; }
        .chat-history { height: 180px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; overflow-y: auto; font-size: 13px; display: flex; flex-direction: column; gap: 8px; }
        .chat-msg { padding: 8px 12px; border-radius: 6px; max-width: 80%; }
        .chat-msg.user { background: #dbeafe; align-self: flex-end; color: #1e40af; }
        .chat-msg.ai { background: #fff; border: 1px solid #e2e8f0; align-self: flex-start; color: #334155; }
        .chat-input-row { display: flex; gap: 8px; }
        .chat-input-row input { flex: 1; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; outline: none; font-size: 13px; }
        .chat-input-row button { background: #2563eb; color: #fff; border: none; padding: 8px 15px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 13px; }
    </style>
</head>
<body>

    <!-- Sidebar -->
    <div class="sidebar">
        <div class="sidebar-brand">
            <i class="fa-solid fa-cube"></i> NEXUS OPS
        </div>
        <ul class="sidebar-menu">
            <li class="active"><i class="fa-solid fa-chart-pie"></i> Dashboard</li>
            <li><i class="fa-solid fa-users-gear"></i> Lead Management</li>
            <li><i class="fa-solid fa-wand-magic-sparkles"></i> Automation</li>
            <li><i class="fa-solid fa-phone-volume"></i> Call Logs</li>
            <li><i class="fa-solid fa-chart-line"></i> Reports</li>
            <li><i class="fa-solid fa-address-book"></i> Contacts</li>
            <li><i class="fa-solid fa-gear"></i> Settings</li>
        </ul>
    </div>

    <!-- Main Content -->
    <div class="main-content">
        <!-- Header -->
        <div class="header">
            <div class="header-title">Welcome, Sarah Chen</div>
            <div class="header-right">
                <div class="user-profile">
                    <img src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100" alt="User">
                    <span>Sarah Chen</span>
                </div>
            </div>
        </div>

        <!-- Dashboard Body -->
        <div class="dashboard-body">
            
            <!-- Status Row -->
            <div class="status-row">
                <div class="status-pill"><span class="dot"></span> Voice Call Automation: ACTIVE</div>
                <div class="status-pill"><span class="dot"></span> WhatsApp API: ACTIVE</div>
            </div>

            <!-- KPI Cards -->
            <div class="kpi-container">
                <div class="kpi-card blue">
                    <div class="kpi-label">Total Leads</div>
                    <div class="kpi-value">12,480</div>
                    <div class="kpi-sub">+8.2% from last week</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Completed Automation Cycles</div>
                    <div class="kpi-value">8,735</div>
                    <div class="kpi-sub" style="color:#2563eb;">70% success rate</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Failed Handshakes</div>
                    <div class="kpi-value">214</div>
                    <div class="kpi-sub" style="color:#dc2626;">2.4% error rate</div>
                </div>
            </div>

            <!-- Grid Layout -->
            <div class="dashboard-grid">
                
                <!-- Left Column: Active Live Leads & AI Tester -->
                <div style="display: flex; flex-direction: column; gap: 20px;">
                    <div class="card">
                        <div class="card-title">
                            <span>Active Live Leads</span>
                            <span style="font-size: 12px; color: #2563eb; cursor: pointer;">Card View</span>
                        </div>
                        <div class="list-item">
                            <div>
                                <strong>Lead: +91 99876 54321</strong>
                                <div style="font-size: 11px; color: #64748b;">Status: Awaiting Call Recording</div>
                            </div>
                            <span class="badge pending">Pending</span>
                        </div>
                        <div class="list-item">
                            <div>
                                <strong>Lead: +91 88776 65544</strong>
                                <div style="font-size: 11px; color: #64748b;">Status: Live Call in Progress</div>
                            </div>
                            <span class="badge progress">In Progress</span>
                        </div>
                        <div class="list-item">
                            <div>
                                <strong>Lead: +91 90012 34567</strong>
                                <div style="font-size: 11px; color: #64748b;">Status: Call Completed</div>
                            </div>
                            <span class="badge success">Success</span>
                        </div>
                    </div>

                    <!-- Gemini AI Live Tester Card -->
                    <div class="card">
                        <div class="card-title"><span>🤖 Gemini AI Command Center</span></div>
                        <div class="chat-section">
                            <div class="chat-history" id="chatBox">
                                <div class="chat-msg ai">Nexus AI operational. Type a prompt to test system response.</div>
                            </div>
                            <div class="chat-input-row">
                                <input type="text" id="userInput" placeholder="Type a message or prompt..." onkeypress="handleKey(event)">
                                <button onclick="sendAIQuery()">Send</button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Right Column: System Config & Call Logs -->
                <div style="display: flex; flex-direction: column; gap: 20px;">
                    <div class="card">
                        <div class="card-title">System Config</div>
                        <div class="config-item">
                            <span>AI Response System</span>
                            <label class="switch"><input type="checkbox" checked><span class="slider"></span></label>
                        </div>
                        <div class="config-item">
                            <span>WhatsApp Bot Status</span>
                            <label class="switch"><input type="checkbox" checked><span class="slider"></span></label>
                        </div>
                        <div style="margin-top: 15px;">
                            <div style="font-size: 12px; color: #64748b; margin-bottom: 5px;">HR Fallback Number</div>
                            <input type="text" value="+91 9988776655" style="width: 100%; padding: 8px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px;" readonly>
                        </div>
                    </div>

                    <div class="card">
                        <div class="card-title"><span>System Call Logs</span></div>
                        <div class="list-item" style="font-size: 12px;">
                            <div>
                                <strong>Outgoing Call to +91 76543 21098</strong>
                                <div style="color: #64748b;">Status: Disconnected</div>
                            </div>
                            <span style="color: #64748b;">10:15 AM</span>
                        </div>
                        <div class="list-item" style="font-size: 12px;">
                            <div>
                                <strong>Incoming Call from +91 91234 56789</strong>
                                <div style="color: #64748b;">Status: Completed</div>
                            </div>
                            <span style="color: #64748b;">10:02 AM</span>
                        </div>
                    </div>
                </div>

            </div>

        </div>
    </div>

    <script>
        async function sendAIQuery() {
            const input = document.getElementById('userInput');
            const chatBox = document.getElementById('chatBox');
            const text = input.value.trim();
            if (!text) return;

            chatBox.innerHTML += `<div class="chat-msg user">${text}</div>`;
            input.value = '';
            chatBox.scrollTop = chatBox.scrollHeight;

            const loadId = 'load_' + Date.now();
            chatBox.innerHTML += `<div class="chat-msg ai" id="${loadId}">Processing...</div>`;
            chatBox.scrollTop = chatBox.scrollHeight;

            try {
                const response = await fetch('/chat-api', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text })
                });
                const data = await response.json();
                document.getElementById(loadId).innerText = data.reply;
            } catch (err) {
                document.getElementById(loadId).innerText = "Error connecting to AI backend.";
            }
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function handleKey(e) {
            if (e.key === 'Enter') sendAIQuery();
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(NEXUS_OPS_HTML)

@app.route('/chat-api', methods=['POST'])
def chat_api():
    data = request.json
    msg_body = data.get('message', '')
    reply_text = "AI response unavailable."
    
    if client and msg_body:
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=msg_body
            )
            if response and response.text:
                reply_text = response.text
        except Exception as e:
            reply_text = f"API Quota/Error: {str(e)}"
            
    return {"reply": reply_text}

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode and token and mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        return 'Webhook active', 200
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
