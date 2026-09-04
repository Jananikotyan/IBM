"""
Sehat Saathi — Full system check script.
Run: python scripts/system_check.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = "[PASS]"
FAIL = "[FAIL]"
results = []

def check(label, fn):
    try:
        fn()
        results.append((label, True, ""))
        print(f"{PASS} {label}")
    except Exception as e:
        results.append((label, False, str(e)))
        print(f"{FAIL} {label}: {e}")


# 1 Config
def _config():
    from app.config import settings
    assert hasattr(settings, "mock_mode")
    assert hasattr(settings, "ollama_mode")
    assert hasattr(settings, "twilio_account_sid")
check("Config loads cleanly", _config)

# 2 Safety layer
def _safety():
    from app.agent.safety_layer import check_red_flags
    assert check_red_flags("chest pain")[0] is True
    assert check_red_flags("I have cough")[0] is False
check("Safety layer (red-flag detection)", _safety)

# 3 Symptom triage tool
def _triage():
    from app.tools.symptom_triage import symptom_triage_tool
    r = symptom_triage_tool.run("fever and headache")
    assert any(w in r for w in ["Self", "See", "Urgent", "care", "tier"])
check("Symptom triage tool", _triage)

# 4 Vaccination schedule tool
def _vax():
    from app.tools.vaccination_schedule import vaccination_schedule_tool
    r = vaccination_schedule_tool.run("6 week old baby")
    assert any(w in r for w in ["OPV", "Pentavalent", "BCG", "week", "vaccine"])
check("Vaccination schedule tool", _vax)

# 5 Emergency escalation
def _emergency():
    from app.tools.emergency_escalation import get_emergency_response
    r = get_emergency_response("cardiac_emergency")
    assert "108" in r
check("Emergency escalation tool", _emergency)

# 6 Language detection
def _lang():
    from app.multilingual.local_translator import detect_language
    assert detect_language("mujhe bukhaar hai") == "hi" or detect_language("\u092e\u0941\u091d\u0947 \u092c\u0941\u0916\u093e\u0930 \u0939\u0948") == "hi"
    assert detect_language("\u0c95\u0ca8\u0ccd\u0ca8\u0ca1 \u0c9c\u0ccd\u0cb5\u0cb0") == "kn"
    assert detect_language("I have fever") == "en"
check("Language detection (en/hi/kn)", _lang)

# 7 MockSehatAgent categories
def _agent_cats():
    from app.agent.mock_agent import MockSehatAgent
    agent = MockSehatAgent()
    test_cases = [
        ("I have fever",             "symptom"),
        ("baby 6 weeks vaccination", "vaccination"),
        ("hospital in Delhi",        "facility"),
        ("chest pain",               "emergency"),
    ]
    for msg, expected_cat in test_cases:
        r = agent.chat(msg, f"chk_{expected_cat}")
        assert r["category"] == expected_cat, \
            f"msg={msg!r}: expected cat={expected_cat}, got {r['category']}"
check("MockSehatAgent — all 4 categories", _agent_cats)

# 8 Location extraction
def _location():
    from app.agent.mock_agent import MockSehatAgent
    agent = MockSehatAgent()
    r = agent.chat("Nearest hospital in Jaipur", "loc_test")
    assert r.get("location") is not None, "Expected location to be extracted"
check("MockSehatAgent — location extraction", _location)

# 9 Analytics tracking
def _analytics():
    from app.analytics import track_query, get_summary
    track_query("ck1", "fever", "en", "symptom", "self_care", False, None)
    track_query("ck2", "emergency", "hi", "emergency", None, True, None)
    track_query("ck3", "hospital in Delhi", "kn", "facility", None, False, "Delhi")
    s = get_summary()
    assert s["total_queries"] >= 3
    assert s["emergency_alerts"] >= 1
    cats = s["category_distribution"]
    assert "symptom" in cats
    assert "emergency" in cats
    assert "facility" in cats
check("Analytics tracking + aggregation", _analytics)

# 10 Heatmap data
def _heatmap():
    from app.analytics import get_disease_heatmap_data
    pts = get_disease_heatmap_data()
    assert len(pts) >= 1
    assert "lat" in pts[0] and "lon" in pts[0]
check("Heatmap data (location-tagged queries)", _heatmap)

# 11 WhatsApp router
def _whatsapp():
    from app.api.whatsapp import router
    assert router.prefix == "/whatsapp"
    paths = [r.path for r in router.routes]
    assert "/whatsapp/incoming" in paths
    assert "/whatsapp/status" in paths
check("WhatsApp router mounted correctly", _whatsapp)

# 12 FastAPI routes
def _routes():
    from app.api.routes import app
    paths = [r.path for r in app.routes]
    required = ["/chat", "/health", "/analytics", "/analytics/heatmap",
                "/whatsapp/incoming", "/clear-memory"]
    for p in required:
        assert p in paths, f"Missing route: {p}"
check("FastAPI — all required routes registered", _routes)

# 13 PDF generator
def _pdf():
    from app.report_generator import generate_pdf
    msgs = [
        {"role": "user",      "content": "I have fever",  "timestamp": "10:00"},
        {"role": "assistant", "content": "See a doctor.",  "timestamp": "10:00",
         "detected_language": "en", "is_emergency": False},
        {"role": "user",      "content": "chest pain",    "timestamp": "10:01"},
        {"role": "assistant", "content": "Call 108 NOW!", "timestamp": "10:01",
         "detected_language": "hi", "is_emergency": True},
    ]
    pdf = generate_pdf(msgs, "test-session-full")
    assert pdf[:4] == b"%PDF", "Invalid PDF header"
    assert len(pdf) > 2000, f"PDF too small: {len(pdf)} bytes"
check("PDF report generator (valid PDF output)", _pdf)

# 14 PDF with multilingual content
def _pdf_multilingual():
    from app.report_generator import generate_pdf
    msgs = [
        {"role": "user",      "content": "mujhe bukhaar hai (Hindi fever)",  "timestamp": "09:00"},
        {"role": "assistant", "content": "Aapko rest karni chahiye.",         "timestamp": "09:00",
         "detected_language": "hi", "is_emergency": False},
        {"role": "user",      "content": "baby 6 weeks old - which vaccine?","timestamp": "09:05"},
        {"role": "assistant", "content": "OPV and Pentavalent are due now.",  "timestamp": "09:05",
         "detected_language": "en", "is_emergency": False},
    ]
    pdf = generate_pdf(msgs, "multilang-session")
    assert pdf[:4] == b"%PDF"
check("PDF generator — multilingual content", _pdf_multilingual)

# ── Summary ────────────────────────────────────────────────────────────────
print()
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
print(f"{'='*45}")
print(f"  {passed}/{len(results)} checks passed   {failed} failed")
print(f"{'='*45}")

if failed:
    print("\nFailed checks:")
    for label, ok, err in results:
        if not ok:
            print(f"  - {label}: {err}")
    sys.exit(1)
else:
    print("\nAll systems go! Sehat Saathi is ready.")
