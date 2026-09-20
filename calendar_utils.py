"""
calendar_utils.py
-------------------
Books site-visit appointments directly onto a Google Calendar using a
service account (no per-user OAuth login needed — good fit for a business
automation bot).

SETUP YOU NEED TO DO (this cannot be automated from code):
1. In Google Cloud Console (same project as your Firebase project, or a new
   one), enable the "Google Calendar API".
2. You can reuse your Firebase service account, or create a new one — either
   way, note its email address, e.g.
   firebase-adminsdk-fbsvc@your-project.iam.gserviceaccount.com
3. Open Google Calendar (the calendar you want site visits booked on) →
   Settings → "Share with specific people" → add that service-account email
   with "Make changes to events" permission.
4. Copy that calendar's ID (Settings → "Integrate calendar" → Calendar ID,
   looks like an email address or a long string ending in
   @group.calendar.google.com) into the GOOGLE_CALENDAR_ID env variable.
5. Set CALENDAR_CREDENTIALS_JSON env var to the same service-account JSON
   content you used for Firebase (or a separate one) — see .env.example.
"""

import os
import json
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID")

_service = None


def _get_service():
    global _service
    if _service is not None:
        return _service

    json_env = os.environ.get("CALENDAR_CREDENTIALS_JSON") or os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if not json_env or not CALENDAR_ID:
        print("[calendar_utils] Missing CALENDAR_CREDENTIALS_JSON or GOOGLE_CALENDAR_ID — "
              "calendar booking is DISABLED.")
        return None

    try:
        cred_dict = json.loads(json_env)
        creds = service_account.Credentials.from_service_account_info(cred_dict, scopes=SCOPES)
        _service = build("calendar", "v3", credentials=creds)
        return _service
    except Exception as e:
        print("[calendar_utils] Failed to init Calendar service:", e)
        return None


def book_site_visit(lead_name: str, phone: str, property_title: str,
                     start_time: datetime.datetime, duration_minutes: int = 30):
    """
    Creates a calendar event for a site visit.
    start_time must be a timezone-aware datetime (Asia/Kolkata recommended).
    Returns the created event's htmlLink on success, or None on failure.
    """
    service = _get_service()
    if not service:
        return None

    end_time = start_time + datetime.timedelta(minutes=duration_minutes)

    event = {
        "summary": f"Site visit: {lead_name or phone} — {property_title}",
        "description": f"Lead phone: {phone}\nProperty: {property_title}\nBooked automatically by WhatsApp AI agent.",
        "start": {"dateTime": start_time.isoformat()},
        "end": {"dateTime": end_time.isoformat()},
    }

    try:
        created = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        return created.get("htmlLink")
    except Exception as e:
        print("[calendar_utils] Booking failed:", e)
        return None


def is_configured() -> bool:
    return _get_service() is not None
