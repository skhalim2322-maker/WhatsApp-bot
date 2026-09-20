"""
whatsapp_utils.py
------------------
Everything related to WhatsApp Cloud API:
- Verifying that incoming webhook requests really came from Meta (HMAC signature)
- Parsing the incoming payload into a simple list of messages
- Sending a reply back to the user
- Marking a message as "read"

Required environment variables:
    WHATSAPP_TOKEN   - permanent/temporary access token for the Cloud API
    PHONE_NUMBER_ID  - your WhatsApp Business phone number ID
    APP_SECRET       - your Meta App's secret (Settings > Basic in the App Dashboard)
                        used ONLY to verify webhook signatures. This is different
                        from WHATSAPP_TOKEN and VERIFY_TOKEN.
"""

import os
import hmac
import hashlib
import requests

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
APP_SECRET = os.environ.get("APP_SECRET")
GRAPH_API_VERSION = os.environ.get("GRAPH_API_VERSION", "v20.0")

GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{PHONE_NUMBER_ID}/messages"


def verify_signature(request_data: bytes, signature_header: str) -> bool:
    """
    Verifies the X-Hub-Signature-256 header Meta sends with every webhook POST.
    Without this check, ANYONE who finds your webhook URL could POST fake
    messages and trigger your bot / burn your Gemini quota.

    If APP_SECRET is not configured, this returns False and logs a warning —
    fail closed, not open.
    """
    if not APP_SECRET:
        print("[whatsapp_utils] WARNING: APP_SECRET not set — rejecting webhook "
              "for safety. Set APP_SECRET to enable signature verification.")
        return False

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_sig = signature_header.split("sha256=")[-1].strip()
    computed_sig = hmac.new(
        APP_SECRET.encode("utf-8"),
        request_data,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_sig, computed_sig)


def parse_incoming_messages(payload: dict):
    """
    Extracts a normalized list of incoming text messages from a WhatsApp
    webhook payload. Returns a list of dicts:
        [{"wa_id": "...", "name": "...", "text": "...", "message_id": "..."}]
    Non-text messages (image, audio, location, etc.) and status updates
    (delivered/read receipts) are safely ignored.
    """
    results = []
    try:
        entries = payload.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages")
                if not messages:
                    continue  # this change was a status update, not a new message

                contacts = value.get("contacts", [])
                name_by_wa_id = {
                    c.get("wa_id"): c.get("profile", {}).get("name")
                    for c in contacts
                }

                for msg in messages:
                    wa_id = msg.get("from")
                    msg_id = msg.get("id")
                    msg_type = msg.get("type")

                    if msg_type == "text":
                        text = msg.get("text", {}).get("body", "")
                    elif msg_type == "button":
                        text = msg.get("button", {}).get("text", "")
                    elif msg_type == "interactive":
                        interactive = msg.get("interactive", {})
                        text = (
                            interactive.get("button_reply", {}).get("title")
                            or interactive.get("list_reply", {}).get("title")
                            or ""
                        )
                    else:
                        # Unsupported type (image/audio/video/location/etc.)
                        text = None

                    results.append({
                        "wa_id": wa_id,
                        "name": name_by_wa_id.get(wa_id),
                        "text": text,
                        "message_id": msg_id,
                        "type": msg_type,
                    })
    except Exception as e:
        print("[whatsapp_utils] Error parsing payload:", e)

    return results


def send_text_message(to: str, body: str) -> bool:
    """Sends a plain text WhatsApp message. Returns True on success."""
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("[whatsapp_utils] Missing WHATSAPP_TOKEN or PHONE_NUMBER_ID — cannot send.")
        return False

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": body[:4096]},  # WhatsApp text messages cap at 4096 chars
    }

    try:
        resp = requests.post(GRAPH_URL, headers=headers, json=payload, timeout=15)
        if resp.status_code >= 400:
            print(f"[whatsapp_utils] Send failed ({resp.status_code}): {resp.text}")
            return False
        return True
    except requests.RequestException as e:
        print("[whatsapp_utils] Send exception:", e)
        return False


def send_image_message(to: str, image_url: str, caption: str = "") -> bool:
    """Sends an image (e.g. a property photo) with an optional caption."""
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("[whatsapp_utils] Missing WHATSAPP_TOKEN or PHONE_NUMBER_ID — cannot send.")
        return False

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "image",
        "image": {"link": image_url, "caption": caption[:1024]},
    }
    try:
        resp = requests.post(GRAPH_URL, headers=headers, json=payload, timeout=15)
        if resp.status_code >= 400:
            print(f"[whatsapp_utils] Image send failed ({resp.status_code}): {resp.text}")
            return False
        return True
    except requests.RequestException as e:
        print("[whatsapp_utils] Image send exception:", e)
        return False


def mark_as_read(message_id: str) -> None:
    """Optional: tells WhatsApp to show the blue double-check to the user."""
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID or not message_id:
        return
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    try:
        requests.post(GRAPH_URL, headers=headers, json=payload, timeout=10)
    except requests.RequestException:
        pass
