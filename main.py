"""
main.py
--------
Dubai link Realty WhatsApp AI Agent — main Flask application.

Flow for a real WhatsApp conversation:
    1. User sends a WhatsApp message -> Meta POSTs it to /webhook
    2. We verify the request really came from Meta (HMAC signature)
    3. We parse the message, save the lead + log it to Firestore
    4. We pull recent conversation history and ask Gemini for a reply
    5. We send that reply back to the user via the WhatsApp Cloud API
    6. We log the AI's reply too, so the next turn has full context

Required environment variables (set these in your host's dashboard, never in code):
    GEMINI_API_KEY            - Google AI Studio / Vertex API key
    WHATSAPP_TOKEN             - WhatsApp Cloud API access token
    PHONE_NUMBER_ID             - WhatsApp Business phone number ID
    APP_SECRET                  - Meta App Secret (for webhook signature verification)
    VERIFY_TOKEN                 - a string YOU make up, used only during webhook setup
    FIREBASE_CREDENTIALS_JSON     - full contents of your Firebase service-account JSON
    DASHBOARD_USERNAME             - username to view the /dashboard (default: admin)
    DASHBOARD_PASSWORD              - password to view the /dashboard (REQUIRED to enable auth)
"""

import os
import datetime
from functools import wraps
from flask import Flask, request, render_template, jsonify, Response
from dateutil import parser as dateutil_parser
from dateutil.tz import gettz

import firebase_utils
import whatsapp_utils
import gemini_utils
import properties_utils
import calendar_utils

IST = gettz("Asia/Kolkata")

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
DASHBOARD_USERNAME = os.environ.get("DASHBOARD_USERNAME", "admin")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD")  # if unset, dashboard auth is OFF (dev only)


# ---------------------------------------------------------------------------
# Simple HTTP Basic Auth for the dashboard (so it isn't public to anyone
# with the URL). Set DASHBOARD_PASSWORD in production.
# ---------------------------------------------------------------------------

def check_auth(username, password):
    return username == DASHBOARD_USERNAME and password == DASHBOARD_PASSWORD


def require_dashboard_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not DASHBOARD_PASSWORD:
            # No password configured -> warn but allow (useful for local dev only)
            return f(*args, **kwargs)
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response(
                "Authentication required.", 401,
                {"WWW-Authenticate": 'Basic realm="Nexus Ops Dashboard"'}
            )
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route('/')
@require_dashboard_auth
def home():
    return render_template("dashboard.html")


@app.route('/api/dashboard-data', methods=['GET'])
@require_dashboard_auth
def dashboard_data():
    stats = firebase_utils.get_dashboard_stats()
    leads = firebase_utils.get_active_leads(limit=10)
    call_logs = firebase_utils.get_recent_call_logs(limit=10)
    return jsonify({
        "stats": stats,
        "leads": leads,
        "call_logs": call_logs,
        "gemini_configured": gemini_utils._client is not None,
    })


@app.route('/chat-api', methods=['POST'])
@require_dashboard_auth
def chat_api():
    """Manual AI tester in the dashboard — NOT the WhatsApp path."""
    data = request.json or {}
    msg_body = data.get('message', '')
    reply_text = gemini_utils.get_real_estate_reply(msg_body)
    return jsonify({"reply": reply_text})


# ---------------------------------------------------------------------------
# WhatsApp Webhook — this is the real bot
# ---------------------------------------------------------------------------

@app.route('/webhook', methods=['GET'])
def webhook_verify():
    """Meta calls this once, when you configure the webhook URL in the App Dashboard."""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode == 'subscribe' and token and VERIFY_TOKEN and token == VERIFY_TOKEN:
        return challenge, 200

    return 'Verification failed', 403


@app.route('/webhook', methods=['POST'])
def webhook_receive():
    """Meta calls this every time a message/status event happens."""
    signature = request.headers.get('X-Hub-Signature-256', '')
    if not whatsapp_utils.verify_signature(request.get_data(), signature):
        print("[webhook] Signature verification FAILED — rejecting request.")
        return 'Invalid signature', 403

    payload = request.get_json(silent=True) or {}
    messages = whatsapp_utils.parse_incoming_messages(payload)

    for msg in messages:
        handle_incoming_message(msg)

    # Always return 200 quickly so Meta doesn't retry/backoff on you
    return "OK", 200


def handle_incoming_message(msg: dict):
    """Full real-estate qualification + property matching + visit-booking flow for one message."""
    wa_id = msg.get("wa_id")
    text = msg.get("text")
    name = msg.get("name")
    message_id = msg.get("message_id")

    if not wa_id:
        return

    whatsapp_utils.mark_as_read(message_id)

    if not text:
        whatsapp_utils.send_text_message(
            wa_id, "मैं अभी सिर्फ text messages पढ़ सकता हूं — कृपया अपना सवाल type करके भेजें।"
        )
        return

    # 1. Load existing lead state + save/update the lead record
    lead_state = firebase_utils.get_lead(wa_id) or {}
    text_en = gemini_utils.translate_to_english(text)
    firebase_utils.upsert_lead(wa_id, name=name, last_message=text, last_message_en=text_en, status="qualifying")
    firebase_utils.log_message(wa_id, role="user", text=text, text_en=text_en)

    # 2. Silently extract any qualification details mentioned in this message
    extracted = gemini_utils.extract_qualification(text)
    firebase_utils.update_qualification_fields(wa_id, {
        "city": extracted.get("city"),
        "locality": extracted.get("locality"),
        "bhk": extracted.get("bhk"),
        "budget_lakh": extracted.get("budget_lakh"),
        "prop_type": extracted.get("prop_type"),
        "timeline": extracted.get("timeline"),
    })
    lead_state = firebase_utils.get_lead(wa_id) or {}

    # 3. If they asked for a site visit and gave a time, try to book it
    if extracted.get("wants_site_visit") and extracted.get("visit_datetime_text"):
        try_book_visit(wa_id, name, lead_state, extracted["visit_datetime_text"])
        return  # booking flow sends its own reply; skip the generic reply below

    # 4. Have we now got enough info (city + bhk + budget) to show matches?
    is_newly_qualified = (
        lead_state.get("city") and lead_state.get("bhk") and lead_state.get("budget_lakh")
        and lead_state.get("status") != "qualified"
    )

    history = firebase_utils.get_recent_history(wa_id, limit=10)
    reply = gemini_utils.get_real_estate_reply(text, history=history, lead_state=lead_state)
    whatsapp_utils.send_text_message(wa_id, reply)
    firebase_utils.log_message(wa_id, role="ai", text=reply)

    if is_newly_qualified:
        send_matching_properties(wa_id, lead_state)
        firebase_utils.upsert_lead(wa_id, status="qualified")


def send_matching_properties(wa_id: str, lead_state: dict):
    """Sends up to 3 matching demo properties as images with captions."""
    matches = properties_utils.match_properties(
        city=lead_state.get("city"),
        bhk=lead_state.get("bhk"),
        budget_lakh=lead_state.get("budget_lakh"),
        prop_type=lead_state.get("prop_type"),
    )

    if not matches:
        whatsapp_utils.send_text_message(
            wa_id, "अभी आपके criteria से match करती हुई property नहीं मिली — हमारी team जल्द ही नई listings के साथ आपसे संपर्क करेगी।"
        )
        return

    for p in matches:
        caption = properties_utils.format_property_text(p)
        whatsapp_utils.send_image_message(wa_id, p["image_url"], caption=caption)
        firebase_utils.log_message(wa_id, role="ai", text=f"[Sent property: {p['title']}]")

    # Remember the top match so a later "book a visit" reply can reference it by name
    firebase_utils.update_qualification_fields(wa_id, {"last_shown_property": matches[0]["title"]})

    followup = "इनमें से कोई पसंद आया? बताइए तो मैं site visit book करवा देता हूं — कौन सा दिन/time आपको सही रहेगा?"
    whatsapp_utils.send_text_message(wa_id, followup)
    firebase_utils.log_message(wa_id, role="ai", text=followup)


def try_book_visit(wa_id: str, name: str, lead_state: dict, datetime_text: str):
    now_ist = datetime.datetime.now(tz=IST)
    iso_guess = gemini_utils.parse_visit_datetime(datetime_text, now_ist.isoformat())

    if not iso_guess:
        reply = "कृपया site visit के लिए exact दिन और time बताएं — जैसे 'कल शाम 5 बजे' या '25 तारीख को दोपहर 12 बजे'।"
        whatsapp_utils.send_text_message(wa_id, reply)
        firebase_utils.log_message(wa_id, role="ai", text=reply)
        return

    try:
        visit_dt = dateutil_parser.isoparse(iso_guess)
        if visit_dt.tzinfo is None:
            visit_dt = visit_dt.replace(tzinfo=IST)
    except Exception:
        reply = "माफ़ कीजिए, वो date/time समझ नहीं आया — कृपया फिर से एक साफ date और time बताएं।"
        whatsapp_utils.send_text_message(wa_id, reply)
        firebase_utils.log_message(wa_id, role="ai", text=reply)
        return

    property_title = lead_state.get("last_shown_property", "Property visit")
    link = calendar_utils.book_site_visit(
        lead_name=name, phone=wa_id, property_title=property_title, start_time=visit_dt
    )

    if link:
        reply = (
            f"✅ आपकी site visit book हो गई है — "
            f"{visit_dt.strftime('%d %b, %I:%M %p')}। हमारी team आपसे confirm करने के लिए संपर्क करेगी।"
        )
        firebase_utils.upsert_lead(wa_id, status="visit_booked", last_message=reply)
    else:
        reply = (
            "आपकी request note कर ली गई है, पर calendar booking अभी configure नहीं है — "
            "हमारी team जल्द आपसे संपर्क करके visit confirm करेगी।"
        )

    whatsapp_utils.send_text_message(wa_id, reply)
    firebase_utils.log_message(wa_id, role="ai", text=reply)


# ---------------------------------------------------------------------------
# Health check (useful for uptime monitors / Render health checks)
# ---------------------------------------------------------------------------

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "gemini_configured": gemini_utils._client is not None,
        "firebase_configured": firebase_utils.init_firebase() is not None,
        "whatsapp_configured": bool(whatsapp_utils.WHATSAPP_TOKEN and whatsapp_utils.PHONE_NUMBER_ID),
    })


if __name__ == '__main__':
    if not VERIFY_TOKEN:
        print("[main] WARNING: VERIFY_TOKEN not set — webhook verification (GET) will always fail.")
    if not os.environ.get("APP_SECRET"):
        print("[main] WARNING: APP_SECRET not set — incoming webhook POSTs will be rejected "
              "until you set it (fail-closed for security).")
    if not DASHBOARD_PASSWORD:
        print("[main] WARNING: DASHBOARD_PASSWORD not set — dashboard is UNAUTHENTICATED. "
              "Set DASHBOARD_USERNAME/DASHBOARD_PASSWORD before deploying publicly.")

    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
