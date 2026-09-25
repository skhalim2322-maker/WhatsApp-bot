"""
firebase_utils.py
------------------
Handles all Firestore interactions:
- Saving/updating leads (each WhatsApp contact who messages in)
- Storing conversation history (for Gemini context + audit trail)
- Storing call logs (populated by whatever voice-automation system you connect later)
- Aggregating stats for the dashboard

SECURITY NOTE:
Never commit your service-account JSON file to source control or paste it into
chat/code. Load it from an environment variable instead. Two supported methods:

1) FIREBASE_CREDENTIALS_JSON — the *entire contents* of your service-account
   JSON file, stored as a single env var (recommended for Render/Railway/etc).
2) GOOGLE_APPLICATION_CREDENTIALS — a file path to the JSON, if your host lets
   you mount secret files (e.g. Render Secret Files, GCP, local dev).

If neither is set, Firestore features are disabled gracefully (the app still
runs — WhatsApp replies still work — you just lose logging/dashboard data).
"""

import os
import json
import datetime
import firebase_admin
from firebase_admin import credentials, firestore

_db = None


def init_firebase():
    """Initialize Firebase Admin SDK exactly once. Returns a Firestore client or None."""
    global _db
    if _db is not None:
        return _db

    if firebase_admin._apps:
        _db = firestore.client()
        return _db

    cred = None
    json_env = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    path_env = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    try:
        if json_env:
            cred_dict = json.loads(json_env)
            cred = credentials.Certificate(cred_dict)
        elif path_env and os.path.exists(path_env):
            cred = credentials.Certificate(path_env)
    except Exception as e:
        print("[firebase_utils] Failed to parse credentials:", e)
        return None

    if cred is None:
        print("[firebase_utils] No Firebase credentials found in environment. "
              "Firestore logging is DISABLED.")
        return None

    try:
        firebase_admin.initialize_app(cred)
        _db = firestore.client()
        print("[firebase_utils] Firebase initialized successfully.")
        return _db
    except Exception as e:
        print("[firebase_utils] Firebase init error:", e)
        return None


def _now():
    return datetime.datetime.utcnow()


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

def upsert_lead(wa_id: str, name: str = None, last_message: str = None,
                 last_message_en: str = None, status: str = "active"):
    """Create or update a lead record for a WhatsApp contact.
    last_message_en is an English translation of last_message, so the business
    owner can read the dashboard in English regardless of what language the
    customer actually wrote in."""
    db = init_firebase()
    if not db:
        return
    ref = db.collection("leads").document(wa_id)
    doc = ref.get()
    data = {
        "wa_id": wa_id,
        "last_message": last_message,
        "status": status,
        "updated_at": _now(),
    }
    if last_message_en:
        data["last_message_en"] = last_message_en
    if name:
        data["name"] = name
    if not doc.exists:
        data["created_at"] = _now()
    ref.set(data, merge=True)


def get_lead(wa_id: str):
    """Returns the full lead document as a dict, or None if it doesn't exist."""
    db = init_firebase()
    if not db:
        return None
    doc = db.collection("leads").document(wa_id).get()
    return doc.to_dict() if doc.exists else None


def update_qualification_fields(wa_id: str, fields: dict):
    """
    Merges newly-extracted qualification fields (bhk, budget_lakh, city,
    locality, timeline, prop_type) into the lead document without
    overwriting fields already known unless a new value is given.
    """
    db = init_firebase()
    if not db:
        return
    clean = {k: v for k, v in fields.items() if v is not None}
    if not clean:
        return
    clean["updated_at"] = _now()
    db.collection("leads").document(wa_id).set(clean, merge=True)


def get_active_leads(limit: int = 10):
    db = init_firebase()
    if not db:
        return []
    docs = (
        db.collection("leads")
        .order_by("updated_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [d.to_dict() for d in docs]


def count_leads():
    db = init_firebase()
    if not db:
        return 0
    # NOTE: for very large collections use a counter document instead of count().
    try:
        return db.collection("leads").count().get()[0][0].value
    except Exception:
        return len(list(db.collection("leads").stream()))


# ---------------------------------------------------------------------------
# Conversation history (per WhatsApp user) — used for Gemini context
# ---------------------------------------------------------------------------

def log_message(wa_id: str, role: str, text: str, text_en: str = None):
    """role is 'user' or 'ai'. text_en is an optional English translation, stored
    so the dashboard can show every conversation in English regardless of the
    customer's actual language."""
    db = init_firebase()
    if not db:
        return
    data = {
        "role": role,
        "text": text,
        "timestamp": _now(),
    }
    if text_en:
        data["text_en"] = text_en
    db.collection("conversations").document(wa_id).collection("messages").add(data)


def get_recent_history(wa_id: str, limit: int = 10):
    """Returns the last `limit` messages, oldest first, for building Gemini context."""
    db = init_firebase()
    if not db:
        return []
    docs = (
        db.collection("conversations").document(wa_id).collection("messages")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    msgs = [d.to_dict() for d in docs]
    msgs.reverse()
    return msgs


# ---------------------------------------------------------------------------
# Call logs — populate these from whatever voice-automation system you wire up.
# This module just exposes read/write helpers; there is no telephony logic here.
# ---------------------------------------------------------------------------

def add_call_log(phone: str, direction: str, status: str):
    db = init_firebase()
    if not db:
        return
    db.collection("call_logs").add({
        "phone": phone,
        "direction": direction,  # "incoming" | "outgoing"
        "status": status,
        "timestamp": _now(),
    })


def get_recent_call_logs(limit: int = 10):
    db = init_firebase()
    if not db:
        return []
    docs = (
        db.collection("call_logs")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [d.to_dict() for d in docs]


# ---------------------------------------------------------------------------
# Dashboard aggregate stats
# ---------------------------------------------------------------------------

def get_dashboard_stats():
    db = init_firebase()
    if not db:
        return {
            "total_leads": 0,
            "completed_cycles": 0,
            "failed_handshakes": 0,
            "firebase_connected": False,
        }
    leads = list(db.collection("leads").stream())
    total_leads = len(leads)
    completed = sum(1 for l in leads if l.to_dict().get("status") == "completed")
    failed = sum(1 for l in leads if l.to_dict().get("status") == "failed")
    return {
        "total_leads": total_leads,
        "completed_cycles": completed,
        "failed_handshakes": failed,
        "firebase_connected": True,
    }
