"""
properties_utils.py
---------------------
Property catalog + matching logic for the real-estate AI agent.

IMPORTANT: The properties below are DEMO/PLACEHOLDER data so you can test the
full flow end-to-end. Replace DEMO_PROPERTIES with your real inventory —
either hardcode your actual listings here, or (better, once you have >20-30
listings) connect this to a real database/sheet. Ask me when you're ready to
wire it to a real data source instead of this static list.

Each property needs at least one publicly reachable image URL for
WhatsApp image messages to work (WhatsApp fetches the image from that URL).
"""

DEMO_PROPERTIES = [
    {
        "id": "prop_001",
        "title": "2BHK Sunrise Residency",
        "city": "Pune",
        "locality": "Wakad",
        "bhk": 2,
        "price_lakh": 65,
        "type": "ready-to-move",
        "image_url": "https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=800",
        "description": "2BHK, 950 sq.ft, ready to move, near IT park.",
    },
    {
        "id": "prop_002",
        "title": "3BHK Green Valley",
        "city": "Pune",
        "locality": "Baner",
        "bhk": 3,
        "price_lakh": 95,
        "type": "under-construction",
        "image_url": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800",
        "description": "3BHK, 1350 sq.ft, possession Dec 2027, clubhouse + pool.",
    },
    {
        "id": "prop_003",
        "title": "1BHK Compact Homes",
        "city": "Pune",
        "locality": "Hinjewadi",
        "bhk": 1,
        "price_lakh": 42,
        "type": "ready-to-move",
        "image_url": "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800",
        "description": "1BHK, 600 sq.ft, walk to IT park, ideal for singles/couples.",
    },
    {
        "id": "prop_004",
        "title": "3BHK Skyline Towers",
        "city": "Mumbai",
        "locality": "Andheri East",
        "bhk": 3,
        "price_lakh": 210,
        "type": "ready-to-move",
        "image_url": "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?w=800",
        "description": "3BHK, 1200 sq.ft, sea-facing, metro connectivity.",
    },
    {
        "id": "prop_005",
        "title": "2BHK Lake View",
        "city": "Mumbai",
        "locality": "Powai",
        "bhk": 2,
        "price_lakh": 145,
        "type": "under-construction",
        "image_url": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=800",
        "description": "2BHK, 850 sq.ft, lake-facing, possession mid-2027.",
    },
]


def match_properties(city: str = None, bhk: int = None,
                      budget_lakh: float = None, prop_type: str = None,
                      limit: int = 3):
    """
    Returns up to `limit` properties matching the given filters.
    Any filter left as None is ignored (not applied).
    budget_lakh is treated as a MAXIMUM budget in lakhs.
    """
    results = []
    for p in DEMO_PROPERTIES:
        if city and city.strip().lower() not in p["city"].lower():
            continue
        if bhk and p["bhk"] != bhk:
            continue
        if budget_lakh and p["price_lakh"] > budget_lakh:
            continue
        if prop_type and prop_type.strip().lower() not in p["type"].lower():
            continue
        results.append(p)

    return results[:limit]


def format_property_text(p: dict) -> str:
    return (
        f"*{p['title']}*\n"
        f"{p['locality']}, {p['city']} — {p['bhk']}BHK\n"
        f"₹{p['price_lakh']} lakh · {p['type'].replace('-', ' ')}\n"
        f"{p['description']}"
    )
