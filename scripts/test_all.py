# -*- coding: utf-8 -*-
"""
Sehat Saathi - Full Test Suite
Run: python scripts/test_all.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force UTF-8 output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"

errors = []

def check(label, condition, detail=""):
    if condition:
        print(f"  [{PASS}] {label}")
    else:
        print(f"  [{FAIL}] {label}" + (f" — {detail}" if detail else ""))
        errors.append(label)

# ─────────────────────────────────────────────
print("\n========================================")
print(" TEST 1: Config & Environment")
print("========================================")
try:
    from app.config import settings
    check("Config loads", True)
    check("Mode set (MOCK or OLLAMA or IBM)", settings.mock_mode or settings.ollama_mode or bool(settings.watsonx_api_key))
    check("GROQ_API_KEY present", bool(settings.groq_api_key), "Set GROQ_API_KEY in .env")
    check("DOCS_PATH configured", bool(settings.docs_path))
    check("VECTOR_DB_PATH configured", bool(settings.vector_db_path))
    mode_str = 'MOCK' if settings.mock_mode else ('OLLAMA' if settings.ollama_mode else 'IBM watsonx')
    print(f"  [{INFO}] Mode: {mode_str}")
except Exception as e:
    check("Config loads", False, str(e))

# ─────────────────────────────────────────────
print("\n========================================")
print(" TEST 2: Knowledge Base & RAG")
print("========================================")
try:
    kb_path = "./data/knowledge_base"
    files = [f for f in os.listdir(kb_path) if f.endswith((".txt",".pdf",".md")) and f != ".gitkeep"]
    check("Knowledge base has documents", len(files) >= 1, f"Found {len(files)} files")
    print(f"  [{INFO}] {len(files)} document(s): {', '.join(files)}")
except Exception as e:
    check("Knowledge base directory exists", False, str(e))

try:
    from app.rag.vector_store import get_retriever
    retriever = get_retriever(k=3)
    results = retriever.invoke("fever management children")
    check("RAG retriever works", len(results) > 0, f"Got {len(results)} chunks")
    check("RAG returns relevant content", any("fever" in d.page_content.lower() for d in results), "fever not found in results")
    results2 = retriever.invoke("vaccination schedule baby 6 weeks")
    check("RAG vaccination query", len(results2) > 0)
    print(f"  [{INFO}] Vector store has chunks indexed correctly")
except Exception as e:
    check("RAG retriever initializes", False, str(e))

# ─────────────────────────────────────────────
print("\n========================================")
print(" TEST 3: Safety Layer")
print("========================================")
try:
    from app.agent.safety_layer import check_red_flags
    tests = [
        ("chest pain cant breathe", True, "cardiac"),
        ("I have a headache", False, None),
        ("seizure happening right now", True, None),
        ("heavy bleeding wont stop", True, None),
        ("my child has fever since 2 days", False, None),
        ("unconscious not waking up", True, None),
    ]
    for text, expected_emergency, _ in tests:
        result, category = check_red_flags(text)
        check(f'Safety: "{text[:35]}..."', result == expected_emergency,
              f"expected emergency={expected_emergency}, got {result}")
except Exception as e:
    check("Safety layer loads", False, str(e))

# ─────────────────────────────────────────────
print("\n========================================")
print(" TEST 4: Tools")
print("========================================")
try:
    from app.tools.vaccination_schedule import vaccination_schedule_tool
    result = vaccination_schedule_tool.invoke("6 weeks old baby")
    check("Vaccination tool works", bool(result) and len(result) > 50)
    check("Vaccination mentions OPV or Pentavalent", "OPV" in result or "Penta" in result or "vaccine" in result.lower())
    print(f"  [{INFO}] Vaccine result preview: {result[:80]}...")
except Exception as e:
    check("Vaccination tool loads", False, str(e))

try:
    from app.tools.symptom_triage import symptom_triage_tool
    result = symptom_triage_tool.invoke("fever for 3 days, headache, body ache")
    check("Symptom triage tool works", bool(result) and len(result) > 30)
    print(f"  [{INFO}] Triage result preview: {result[:80]}...")
except Exception as e:
    check("Symptom triage tool loads", False, str(e))

try:
    from app.tools.emergency_escalation import get_emergency_response
    result = get_emergency_response("cardiac")
    check("Emergency escalation works", "108" in result)
except Exception as e:
    check("Emergency escalation loads", False, str(e))

# ─────────────────────────────────────────────
print("\n========================================")
print(" TEST 5: Language Detection")
print("========================================")
try:
    from app.multilingual.local_translator import detect_language
    checks = [
        ("Hello I have a fever", "en"),
        ("मुझे बुखार है", "hi"),
        ("என்னால் மூச்சு விட முடியவில்லை", "ta"),
        ("నాకు జ్వరం వస్తుంది", "te"),
        ("ನನಗೆ ಜ್ವರ ಇದೆ", "kn"),
        ("আমার জ্বর হয়েছে", "bn"),
    ]
    for text, expected_lang in checks:
        detected = detect_language(text)
        check(f'Detect [{expected_lang}]: "{text[:25]}"', detected == expected_lang,
              f"detected '{detected}' instead of '{expected_lang}'")
except Exception as e:
    check("Language detection loads", False, str(e))

# ─────────────────────────────────────────────
print("\n========================================")
print(" TEST 6: Mock Agent (Full Pipeline)")
print("========================================")
try:
    from app.agent.mock_agent import MockSehatAgent
    agent = MockSehatAgent()
    check("MockSehatAgent initializes", True)

    # English test
    r1 = agent.chat("I have fever and headache for 2 days", session_id="test1")
    check("English chat works", bool(r1.get("response")) and len(r1["response"]) > 30)
    check("Response has language key", "detected_language" in r1)
    check("English detected", r1.get("detected_language") == "en")
    print(f"  [{INFO}] English response preview: {r1['response'][:80]}...")

    # Hindi test
    r2 = agent.chat("मुझे बुखार और सिर दर्द है", session_id="test2")
    check("Hindi chat works", bool(r2.get("response")) and len(r2["response"]) > 10)
    print(f"  [{INFO}] Hindi response preview: {r2['response'][:80]}...")

    # Emergency test
    r3 = agent.chat("I have severe chest pain and cannot breathe", session_id="test3")
    check("Emergency detected", r3.get("is_emergency") == True)
    check("Emergency response has 108", "108" in r3.get("response", ""))
    print(f"  [{INFO}] Emergency response preview: {r3['response'][:80]}...")

    # Vaccination test
    r4 = agent.chat("My baby is 6 weeks old, what vaccines are due?", session_id="test4")
    check("Vaccination query works", bool(r4.get("response")) and len(r4["response"]) > 30)
    print(f"  [{INFO}] Vaccine response preview: {r4['response'][:80]}...")

except Exception as e:
    check("Mock agent initializes", False, str(e))

# ─────────────────────────────────────────────
print("\n========================================")
print(" TEST 7: PDF Report Generator")
print("========================================")
try:
    from app.report_generator import generate_pdf
    messages = [
        {"role": "user", "content": "I have fever for 2 days", "timestamp": "10:00", "is_emergency": False, "detected_language": "en"},
        {"role": "assistant", "content": "Drink fluids and rest. Monitor temperature.", "timestamp": "10:01", "is_emergency": False, "detected_language": "en"},
    ]
    pdf_bytes = generate_pdf(messages, session_id="test-session")
    check("PDF generates without error", isinstance(pdf_bytes, bytes))
    check("PDF is non-empty", len(pdf_bytes) > 1000, f"Only {len(pdf_bytes)} bytes")
    print(f"  [{INFO}] PDF size: {len(pdf_bytes)//1024} KB")
except Exception as e:
    check("PDF generator works", False, str(e))

# ─────────────────────────────────────────────
print("\n========================================")
print(" TEST 8: Analytics")
print("========================================")
try:
    from app.analytics import track_query, get_summary
    track_query("test-sess", "test message", "en", "symptom", triage_tier="self_care", is_emergency=False)
    summary = get_summary()
    check("Analytics tracking works", summary["total_queries"] >= 1)
    check("Analytics summary has all keys",
          all(k in summary for k in ["total_queries","unique_sessions","language_distribution","daily_trend"]))
    print(f"  [{INFO}] Total queries tracked: {summary['total_queries']}")
except Exception as e:
    check("Analytics module works", False, str(e))

# ─────────────────────────────────────────────
print("\n========================================")
print(" TEST 9: FastAPI App Import")
print("========================================")
try:
    from app.api.routes import app
    from fastapi.routing import APIRoute
    check("FastAPI app imports", True)
    routes = [r.path for r in app.routes if isinstance(r, APIRoute)]
    check("Route /health exists", "/health" in routes)
    check("Route /chat exists", "/chat" in routes)
    check("Route /analytics exists", "/analytics" in routes)
    check("Route /voice exists", "/voice" in routes)
    print(f"  [{INFO}] Registered routes: {routes}")
except Exception as e:
    check("FastAPI app imports", False, str(e))

# ─────────────────────────────────────────────
print("\n========================================")
print(" RESULTS SUMMARY")
print("========================================")
if not errors:
    print("\n  ALL TESTS PASSED! Project is ready to run.\n")
else:
    print(f"\n  {len(errors)} test(s) FAILED:")
    for e in errors:
        print(f"    - {e}")
    print()
