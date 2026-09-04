"""
Sehat Saathi - Analytics Store
================================
Lightweight in-memory + JSON-persisted analytics tracking.
Records every query for the dashboard: language, category, triage tier,
emergency flag, and timestamp.

No external dependencies — stdlib only (json, datetime, collections).
"""
import json
import os
import logging
from datetime import datetime, date
from collections import defaultdict, Counter
from typing import Dict, List, Optional
import threading

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Storage — JSON file next to this module
# ---------------------------------------------------------------------------
_DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "analytics.json")
_lock = threading.Lock()

_store: Dict = {
    "queries": [],          # list of event dicts
    "total": 0,
}


def _load() -> None:
    """Load persisted analytics from disk (called once at startup)."""
    global _store
    path = os.path.abspath(_DATA_FILE)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                _store["queries"] = data.get("queries", [])
                _store["total"] = len(_store["queries"])
        except Exception as e:
            logger.warning("Could not load analytics file: %s", e)


def _save() -> None:
    """Persist analytics to disk (non-blocking best-effort)."""
    path = os.path.abspath(_DATA_FILE)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"queries": _store["queries"][-5000:]}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Could not save analytics: %s", e)


# Load on import
_load()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def track_query(
    session_id: str,
    message: str,
    detected_language: str,
    category: str,           # e.g. "symptom", "vaccination", "facility", "emergency", "general"
    triage_tier: Optional[str] = None,   # "self_care" / "see_doctor" / "urgent"
    is_emergency: bool = False,
    location: Optional[str] = None,
) -> None:
    """Record one user query event."""
    event = {
        "ts": datetime.utcnow().isoformat(),
        "date": date.today().isoformat(),
        "session_id": session_id,
        "lang": detected_language,
        "category": category,
        "triage_tier": triage_tier,
        "is_emergency": is_emergency,
        "location": location,
        "msg_len": len(message),
    }
    with _lock:
        _store["queries"].append(event)
        _store["total"] += 1
        # Persist every 10 queries to keep disk writes low
        if _store["total"] % 10 == 0:
            _save()


def get_summary() -> Dict:
    """Return aggregated stats for the dashboard."""
    with _lock:
        queries = list(_store["queries"])

    if not queries:
        return _empty_summary()

    total = len(queries)
    lang_counts = Counter(q["lang"] for q in queries)
    cat_counts = Counter(q["category"] for q in queries)
    triage_counts = Counter(q["triage_tier"] for q in queries if q.get("triage_tier"))
    emergency_count = sum(1 for q in queries if q.get("is_emergency"))

    # Daily trend — last 14 days
    daily: Dict[str, int] = defaultdict(int)
    for q in queries:
        daily[q.get("date", "unknown")] += 1
    sorted_dates = sorted(daily.keys())[-14:]
    daily_trend = {"dates": sorted_dates, "counts": [daily[d] for d in sorted_dates]}

    # Unique sessions
    unique_sessions = len(set(q["session_id"] for q in queries))

    # Top symptoms / categories today
    today = date.today().isoformat()
    today_queries = [q for q in queries if q.get("date") == today]

    return {
        "total_queries": total,
        "unique_sessions": unique_sessions,
        "emergency_alerts": emergency_count,
        "language_distribution": dict(lang_counts.most_common(10)),
        "category_distribution": dict(cat_counts.most_common(10)),
        "triage_distribution": dict(triage_counts),
        "daily_trend": daily_trend,
        "today_count": len(today_queries),
        "today_emergencies": sum(1 for q in today_queries if q.get("is_emergency")),
    }


def get_disease_heatmap_data() -> List[Dict]:
    """
    Return symptom/category events with location for the heatmap.
    Filters to only events that have a location tag.
    """
    with _lock:
        queries = list(_store["queries"])

    # Known city → approximate lat/lon for demo
    CITY_COORDS = {
        "delhi": (28.6139, 77.2090),
        "mumbai": (19.0760, 72.8777),
        "bangalore": (12.9716, 77.5946),
        "bengaluru": (12.9716, 77.5946),
        "chennai": (13.0827, 80.2707),
        "kolkata": (22.5726, 88.3639),
        "hyderabad": (17.3850, 78.4867),
        "pune": (18.5204, 73.8567),
        "jaipur": (26.9124, 75.7873),
        "lucknow": (26.8467, 80.9462),
        "patna": (25.5941, 85.1376),
        "bhopal": (23.2599, 77.4126),
        "nagpur": (21.1458, 79.0882),
        "ahmedabad": (23.0225, 72.5714),
        "surat": (21.1702, 72.8311),
        "chandigarh": (30.7333, 76.7794),
        "kochi": (9.9312, 76.2673),
        "visakhapatnam": (17.6868, 83.2185),
    }

    heatmap = []
    for q in queries:
        loc = (q.get("location") or "").lower().strip()
        if not loc:
            continue
        coords = None
        for city, latlon in CITY_COORDS.items():
            if city in loc:
                coords = latlon
                break
        if coords:
            heatmap.append({
                "lat": coords[0],
                "lon": coords[1],
                "category": q.get("category", "general"),
                "is_emergency": q.get("is_emergency", False),
                "date": q.get("date"),
                "location": loc,
            })

    return heatmap


def _empty_summary() -> Dict:
    return {
        "total_queries": 0,
        "unique_sessions": 0,
        "emergency_alerts": 0,
        "language_distribution": {},
        "category_distribution": {},
        "triage_distribution": {},
        "daily_trend": {"dates": [], "counts": []},
        "today_count": 0,
        "today_emergencies": 0,
    }
