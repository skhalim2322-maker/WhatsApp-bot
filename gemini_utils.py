"""
gemini_utils.py
-----------------
Two jobs, kept separate on purpose:

1. get_real_estate_reply() — the conversational reply the lead actually sees.
   Persona: a real-estate assistant that naturally asks for whatever
   qualification info is still missing (BHK, budget, city/locality, timeline).

2. extract_qualification() — a silent, structured-JSON call that reads the
   lead's latest message and pulls out any of those fields they mentioned,
   so we can save them to Firestore. The lead never sees this call.

Splitting these two means the visible reply stays natural and conversational,
while the data extraction stays reliable and structured.
"""

import os
import json
import re
from google import genai

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

_client = None
if API_KEY:
    try:
        _client = genai.Client(api_key=API_KEY)
    except Exception as e:
        print("[gemini_utils] Gemini Client Init Error:", e)
else:
    print("[gemini_utils] WARNING: GEMINI_API_KEY not set — AI replies disabled.")


AGENCY_NAME = os.environ.get("AGENCY_NAME", "our agency")

REAL_ESTATE_PERSONA = (
    f"You are a friendly, efficient real-estate assistant for {AGENCY_NAME}, chatting on WhatsApp. "
    "Your goal is to naturally find out: which city/locality they want, how many BHK, their budget "
    "(in lakhs), and whether they want ready-to-move or under-construction, and roughly when they plan "
    "to buy. Ask ONE missing question at a time, conversationally — never a long form. "
    "Once you have enough info, tell them you're finding matching properties. "
    "Keep replies short (2-4 lines), warm, and professional. "
    "LANGUAGE RULE (strict, follow exactly): detect the language of the user's LATEST message and reply "
    "in that exact language. If they wrote in English, reply ONLY in English. If they wrote in Hindi "
    "(Devanagari script), reply in Hindi. If they wrote in Hinglish (Roman-script Hindi/English mix), "
    "reply in Hinglish. Do not default to Hindi — match the user's own message, not the conversation's "
    "earlier language."
)


import re

# Unicode script ranges for major Indian languages + Arabic/Urdu.
# Script-based detection is very reliable (no ambiguity like Latin script has).
SCRIPT_RANGES = [
    (r"[\u0980-\u09FF]", "Bengali"),
    (r"[\u0A00-\u0A7F]", "Punjabi"),
    (r"[\u0A80-\u0AFF]", "Gujarati"),
    (r"[\u0B00-\u0B7F]", "Odia"),
    (r"[\u0B80-\u0BFF]", "Tamil"),
    (r"[\u0C00-\u0C7F]", "Telugu"),
    (r"[\u0C80-\u0CFF]", "Kannada"),
    (r"[\u0D00-\u0D7F]", "Malayalam"),
    (r"[\u0600-\u06FF\u0750-\u077F]", "Arabic"),  # also covers Urdu script
    (r"[\u0900-\u097F]", "Hindi"),  # Devanagari — checked last among scripts (Marathi also uses this)
]


def detect_language(text: str) -> str:
    """
    Reliable language detection — doesn't rely on the AI model for native scripts.
    Returns a language name: 'Hindi', 'Hinglish', 'English', 'Bengali', 'Tamil',
    'Telugu', 'Kannada', 'Malayalam', 'Gujarati', 'Punjabi', 'Odia', 'Arabic', etc.
    For Latin-script text that isn't clearly English or Hinglish, returns None so
    the caller can fall back to asking the AI model to identify it (covers Marathi,
    Tamil, etc. typed in Roman script, which script-detection can't catch).
    """
    if not text:
        return "English"

    for pattern, lang_name in SCRIPT_RANGES:
        if re.search(pattern, text):
            return lang_name

    # Common Hinglish (Roman-script Hindi) words/markers
    hinglish_markers = [
        "hai", "hain", "kya", "kaise", "chahiye", "nahi", "nahin", "bhi",
        "mujhe", "aap", "aapka", "kar", "karo", "karna", "mein", "mai",
        "hoon", "ho", "ka", "ki", "ke", "se", "ye", "yeh", "woh", "wo",
        "abhi", "matlab", "theek", "thik", "haan", "nahi", "budget",
        "chahta", "chahti",
    ]
    words = re.findall(r"[a-zA-Z']+", text.lower())
    hinglish_hits = sum(1 for w in words if w in hinglish_markers)

    if words and hinglish_hits / len(words) >= 0.15:
        return "Hinglish"

    return None  # ambiguous Latin-script text — caller should ask the AI model


def identify_language_ai(text: str) -> str:
    """
    Fallback for Latin-script messages that script-detection and the Hinglish
    heuristic couldn't confidently classify (e.g. Marathi, Tamil, or Bengali
    typed in Roman letters instead of native script). Uses the AI model itself,
    which is very good at this. Falls back to 'English' if anything goes wrong.
    """
    if not _client or not text:
        return "English"
    try:
        prompt = (
            "What language is the following WhatsApp message written in? "
            "Reply with ONLY the language name in English (e.g. 'English', "
            "'Marathi', 'Tamil', 'Bengali'), nothing else.\n\n"
            f"Message: \"{text}\""
        )
        response = _client.models.generate_content(model=MODEL_NAME, contents=prompt)
        result = (response.text or "").strip().split("\n")[0].strip(" .\"'")
        return result or "English"
    except Exception as e:
        print("[gemini_utils] Language identification error:", e)
        return "English"


def get_language_for_reply(text: str) -> str:
    """
    Best-effort language instruction to use for a reply — script check first,
    then AI fallback. Hindi is deliberately returned as Romanized Hindi
    (Hinglish, English/Roman letters) instead of Devanagari script — many
    readers can sound out Roman letters but not read Devanagari fluently.
    """
    lang = detect_language(text)
    if lang is None:
        lang = identify_language_ai(text)
    if lang == "Hindi":
        return "Hindi, but written using English/Roman alphabet letters (Romanized Hindi / Hinglish) — NOT Devanagari script"
    return lang


def translate_to_english(text: str) -> str:
    """
    Translates any-language customer message into Romanized Hindi (Hindi
    meaning, written using English/Roman letters, NOT Devanagari) — used so
    the business owner can read every conversation in the dashboard in a
    script they're comfortable with, regardless of what language/script the
    customer actually wrote in. Returns the original text unchanged if
    translation isn't available.
    """
    if not _client or not text:
        return text
    try:
        prompt = (
            "Translate the following message into Hindi, but write the Hindi "
            "using English/Roman alphabet letters (Romanized Hindi / Hinglish), "
            "NOT Devanagari script. If the message is already Romanized Hindi "
            "or English, you may return it unchanged if that's clearer. Reply "
            "with ONLY the translation, nothing else — no notes, no language name.\n\n"
            f"Message: \"{text}\""
        )
        response = _client.models.generate_content(model=MODEL_NAME, contents=prompt)
        result = (response.text or "").strip()
        return result or text
    except Exception as e:
        print("[gemini_utils] Translation error:", e)
        return text


def _build_reply_prompt(user_message: str, history: list, lead_state: dict) -> str:
    known = []
    missing = []
    for field, label in [("city", "city/locality"), ("bhk", "BHK"),
                          ("budget_lakh", "budget"), ("prop_type", "ready-to-move vs under-construction"),
                          ("timeline", "purchase timeline")]:
        if lead_state.get(field):
            known.append(f"{label}: {lead_state.get(field)}")
        else:
            missing.append(label)

    lines = [REAL_ESTATE_PERSONA, ""]
    if known:
        lines.append("Already known about this lead: " + "; ".join(known))
    if missing:
        lines.append("Still need to find out: " + ", ".join(missing))
    lines.append("")

    if history:
        lines.append("Recent conversation:")
        for turn in history:
            speaker = "Lead" if turn.get("role") == "user" else "Assistant"
            lines.append(f"{speaker}: {turn.get('text', '')}")
        lines.append("")

    lines.append(f"Lead: {user_message}")
    detected_lang = get_language_for_reply(user_message)
    lines.append(
        f"[SYSTEM: The lead's message above is in {detected_lang}. "
        f"You MUST write your reply ONLY in {detected_lang}, regardless of what "
        f"language earlier turns used. Do not mix in Hindi if this is English.]"
    )
    lines.append("Assistant:")
    return "\n".join(lines)


def get_real_estate_reply(user_message: str, history: list = None, lead_state: dict = None) -> str:
    if not _client:
        return "माफ़ कीजिए, AI assistant अभी उपलब्ध नहीं है। हमारी टीम जल्द ही आपसे संपर्क करेगी।"

    prompt = _build_reply_prompt(user_message, history or [], lead_state or {})

    try:
        response = _client.models.generate_content(model=MODEL_NAME, contents=prompt)
        if response and response.text:
            return response.text.strip()
        return "माफ़ कीजिए, अभी जवाब नहीं बन पाया। कृपया दोबारा भेजें।"
    except Exception as e:
        print("[gemini_utils] Generation error:", e)
        return "कुछ तकनीकी दिक्कत आई है, कृपया थोड़ी देर में फिर से कोशिश करें।"


EXTRACTION_PROMPT_TEMPLATE = """Extract real-estate lead qualification details from this WhatsApp message.
Return ONLY a valid JSON object, nothing else — no explanation, no markdown fences.

Fields (use null for anything not mentioned in THIS message):
- city: string or null (e.g. "Pune", "Mumbai")
- locality: string or null (e.g. "Wakad", "Baner")
- bhk: integer or null (1, 2, 3, 4...)
- budget_lakh: number or null (convert to lakhs, e.g. "70 lakh" -> 70, "1.2 crore" -> 120)
- prop_type: one of "ready-to-move", "under-construction", or null
- timeline: string or null (e.g. "next month", "3 months", "just browsing")
- wants_site_visit: true if they are asking to visit/see a property in person, else false
- visit_datetime_text: string or null — verbatim text describing when they want to visit, if any

Message: "{message}"

JSON:"""


def extract_qualification(user_message: str) -> dict:
    """Returns a dict of extracted fields. Any field the model didn't find is omitted/null."""
    default = {
        "city": None, "locality": None, "bhk": None, "budget_lakh": None,
        "prop_type": None, "timeline": None, "wants_site_visit": False,
        "visit_datetime_text": None,
    }
    if not _client or not user_message:
        return default

    prompt = EXTRACTION_PROMPT_TEMPLATE.format(message=user_message.replace('"', "'"))

    try:
        response = _client.models.generate_content(model=MODEL_NAME, contents=prompt)
        text = (response.text or "").strip()
        text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
        parsed = json.loads(text)
        default.update({k: v for k, v in parsed.items() if k in default})
        return default
    except Exception as e:
        print("[gemini_utils] Extraction error:", e)
        return default


DATETIME_PROMPT_TEMPLATE = """The current date/time is {now}, timezone Asia/Kolkata.
A person said: "{text}"
This describes when they want a site visit. Convert it to a single future
ISO 8601 datetime (Asia/Kolkata, e.g. 2026-09-25T16:00:00+05:30). Assume a
reasonable time of day (e.g. "tomorrow" -> 11:00, "evening" -> 18:00) if no
exact time was given. If the text is too vague to resolve to a date at all,
return exactly: null

Return ONLY the ISO datetime string or the word null — nothing else."""


def parse_visit_datetime(text: str, now_iso: str) -> str:
    """Returns an ISO 8601 datetime string, or None if it couldn't be resolved."""
    if not _client or not text:
        return None
    prompt = DATETIME_PROMPT_TEMPLATE.format(now=now_iso, text=text.replace('"', "'"))
    try:
        response = _client.models.generate_content(model=MODEL_NAME, contents=prompt)
        result = (response.text or "").strip().strip('"')
        if result.lower() == "null" or not result:
            return None
        return result
    except Exception as e:
        print("[gemini_utils] Datetime parse error:", e)
        return None
