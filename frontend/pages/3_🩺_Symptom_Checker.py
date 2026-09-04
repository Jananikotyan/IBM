"""
Sehat Saathi — 🩺 Symptom Checker Wizard
==========================================
Step-by-step guided symptom form:
  Step 1 → Body area selection (visual grid)
  Step 2 → Symptom selection (filtered by body area)
  Step 3 → Duration picker
  Step 4 → Severity slider
  Result → Visual triage card + recommended action
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st

st.set_page_config(
    page_title="Sehat Saathi – Symptom Checker",
    page_icon="🩺",
    layout="wide",
)

# ── symptom database ──────────────────────────────────────────────────────────
BODY_AREAS = {
    "🧠 Head & Neck":   ["headache", "stiff neck", "sore throat", "earache", "eye pain", "eye discharge", "dizziness", "light sensitivity"],
    "🫁 Chest":          ["chest pain", "chest discomfort", "cough", "wheezing", "rapid breathing", "shortness of breath"],
    "🫃 Abdomen":        ["abdominal pain", "nausea", "vomiting", "diarrhea", "loose stool", "blood in stool", "indigestion", "heartburn"],
    "💪 Limbs & Skin":  ["joint pain", "muscle ache", "body ache", "swelling", "rash", "minor cut", "bruise"],
    "🌡️ Whole Body":    ["fever", "high fever", "fatigue", "extreme weakness", "chills", "night sweats", "weight loss"],
    "🚽 Urinary":        ["burning urine", "pain urinating", "dark urine", "no urine", "blood in urine"],
    "👶 Child / Baby":  ["baby fever", "child fever", "newborn sick", "child not eating", "child vomiting"],
    "🤰 Pregnancy":     ["pregnant fever", "pregnant bleeding", "pregnancy pain"],
}

DURATION_OPTIONS = [
    "Just started (today)",
    "1–2 days",
    "3–5 days",
    "About a week",
    "More than 2 weeks",
]

SEVERITY_LABELS = {
    1: ("Barely noticeable", "#22c55e"),
    2: ("Mild — not affecting daily life", "#86efac"),
    3: ("Moderate — slowing me down", "#fbbf24"),
    4: ("Severe — hard to function", "#f97316"),
    5: ("Unbearable / emergency", "#ef4444"),
}

# ── triage engine (mirrors symptom_triage_tool logic) ────────────────────────
def compute_triage(symptoms: list, duration: str, severity: int) -> dict:
    """
    Compute triage tier from wizard selections without going through the LangChain tool.
    Returns dict with tier (1/2/3), label, colour, explanation, actions.
    """
    text = " ".join(symptoms) + " " + duration

    # Tier 3 triggers
    T3_KEYWORDS = [
        "chest pain", "rapid breathing", "shortness of breath", "wheezing",
        "high fever", "baby fever", "newborn sick", "pregnant fever",
        "pregnant bleeding", "blood in stool", "blood in urine", "vomiting blood",
        "stiff neck", "light sensitivity", "extreme weakness", "no urine",
        "bluish", "jaundice", "dizziness",
    ]
    # Tier 2 triggers
    T2_KEYWORDS = [
        "fever", "cough", "rash", "swelling", "diarrhea", "vomiting", "nausea",
        "joint pain", "body ache", "burning urine", "dark urine", "earache",
        "eye pain", "sore throat", "abdominal pain", "chills", "night sweats",
        "weight loss", "child fever", "child vomiting",
    ]

    tier = 1
    for kw in T3_KEYWORDS:
        if kw in text.lower():
            tier = 3
            break
    if tier < 3:
        for kw in T2_KEYWORDS:
            if kw in text.lower():
                tier = 2
                break

    # Severity bump: severity 4-5 bumps tier up by 1
    if severity >= 4 and tier < 3:
        tier += 1
    # Duration bump: >2 weeks bumps tier 1 → 2
    if "2 weeks" in duration and tier == 1:
        tier = 2

    TIERS = {
        1: {
            "label":  "✅ Self-care at home",
            "color":  "#16a34a",
            "bg":     "#f0fdf4",
            "border": "#86efac",
            "icon":   "🏠",
            "explanation": (
                "Your symptoms appear mild and can likely be managed with rest and fluids at home. "
                "Monitor closely — if things worsen or persist beyond 3 days, see a doctor."
            ),
            "actions": [
                "💧 Drink plenty of fluids — water, ORS, or coconut water",
                "😴 Get adequate rest",
                "🌡️ Monitor temperature twice a day",
                "🚫 Do NOT self-medicate with antibiotics",
                "📞 Call 104 if you need health guidance",
            ],
        },
        2: {
            "label":  "🟡 See a doctor within a few days",
            "color":  "#b45309",
            "bg":     "#fefce8",
            "border": "#fde047",
            "icon":   "🏥",
            "explanation": (
                "Your symptoms need a doctor's evaluation. This is not an immediate emergency, "
                "but please visit your nearest Primary Health Centre (PHC) or clinic within 1–2 days."
            ),
            "actions": [
                "🏥 Visit your nearest PHC — consultations are FREE at government centres",
                "📋 Note down all your symptoms and when they started",
                "💧 Stay hydrated in the meantime",
                "🚫 Do not take prescription medicines without a doctor",
                "📞 Call 104 (National Health Helpline) for guidance",
            ],
        },
        3: {
            "label":  "🔴 Seek urgent care now",
            "color":  "#b91c1c",
            "bg":     "#fef2f2",
            "border": "#fca5a5",
            "icon":   "🚨",
            "explanation": (
                "Your symptoms may indicate a serious condition requiring prompt medical attention. "
                "Go to the nearest hospital or emergency department immediately, "
                "or call 108 for a free ambulance."
            ),
            "actions": [
                "🚑 Call 108 NOW for a free ambulance",
                "🏥 Go to the nearest hospital emergency department",
                "👨‍👩‍👧 Ask someone to accompany you — do not go alone",
                "📋 Bring any medicines you currently take",
                "📞 Call 104 if you need help locating the nearest hospital",
            ],
        },
    }
    return TIERS[tier]


# ── session state ─────────────────────────────────────────────────────────────
if "wiz_step" not in st.session_state:
    st.session_state.wiz_step = 1
if "wiz_area" not in st.session_state:
    st.session_state.wiz_area = None
if "wiz_symptoms" not in st.session_state:
    st.session_state.wiz_symptoms = []
if "wiz_duration" not in st.session_state:
    st.session_state.wiz_duration = None
if "wiz_severity" not in st.session_state:
    st.session_state.wiz_severity = 2
if "wiz_result" not in st.session_state:
    st.session_state.wiz_result = None

# ── header ────────────────────────────────────────────────────────────────────
st.markdown("## 🩺 Symptom Checker Wizard")
st.caption("Answer 4 quick questions — get an instant triage recommendation")
st.divider()

# ── progress bar ──────────────────────────────────────────────────────────────
step = st.session_state.wiz_step
STEPS = ["Body Area", "Symptoms", "Duration", "Severity", "Result"]
progress = (step - 1) / (len(STEPS) - 1)

cols_prog = st.columns(len(STEPS))
for i, label in enumerate(STEPS):
    s = i + 1
    if s < step:
        cols_prog[i].markdown(f"<div style='text-align:center;color:#16a34a;font-size:12px;font-weight:700'>✓ {label}</div>", unsafe_allow_html=True)
    elif s == step:
        cols_prog[i].markdown(f"<div style='text-align:center;color:#3b82d4;font-size:12px;font-weight:700;border-bottom:2px solid #3b82d4;padding-bottom:4px'>● {label}</div>", unsafe_allow_html=True)
    else:
        cols_prog[i].markdown(f"<div style='text-align:center;color:#9ca3af;font-size:12px'>○ {label}</div>", unsafe_allow_html=True)

st.progress(progress)
st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Body Area
# ══════════════════════════════════════════════════════════════════════════════
if step == 1:
    st.markdown("### Step 1 — Where is the problem?")
    st.caption("Select the body area that best describes your main concern")
    st.markdown("")

    areas = list(BODY_AREAS.keys())
    cols = st.columns(4)
    for i, area in enumerate(areas):
        if cols[i % 4].button(area, use_container_width=True, key=f"area_{i}"):
            st.session_state.wiz_area = area
            st.session_state.wiz_symptoms = []
            st.session_state.wiz_step = 2
            st.rerun()

    st.markdown("")
    st.info("💡 Select the area where you feel the most discomfort")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Symptoms
# ══════════════════════════════════════════════════════════════════════════════
elif step == 2:
    area = st.session_state.wiz_area
    st.markdown(f"### Step 2 — What symptoms do you have? ({area})")
    st.caption("Select all that apply")
    st.markdown("")

    symptom_list = BODY_AREAS[area]
    selected = list(st.session_state.wiz_symptoms)

    cols = st.columns(2)
    for i, sym in enumerate(symptom_list):
        checked = cols[i % 2].checkbox(sym.capitalize(), value=(sym in selected), key=f"sym_{i}")
        if checked and sym not in selected:
            selected.append(sym)
        elif not checked and sym in selected:
            selected.remove(sym)

    st.session_state.wiz_symptoms = selected
    st.markdown("")

    col_back, col_next = st.columns([1, 3])
    if col_back.button("← Back", use_container_width=True):
        st.session_state.wiz_step = 1
        st.rerun()
    if col_next.button("Next →", use_container_width=True, disabled=(len(selected) == 0)):
        st.session_state.wiz_step = 3
        st.rerun()

    if not selected:
        st.caption("⚠️ Please select at least one symptom to continue")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Duration
# ══════════════════════════════════════════════════════════════════════════════
elif step == 3:
    st.markdown("### Step 3 — How long have you had these symptoms?")
    st.caption(f"Selected: {', '.join(st.session_state.wiz_symptoms)}")
    st.markdown("")

    duration = st.radio(
        "Duration",
        options=DURATION_OPTIONS,
        index=DURATION_OPTIONS.index(st.session_state.wiz_duration)
              if st.session_state.wiz_duration in DURATION_OPTIONS else 0,
        label_visibility="collapsed",
    )
    st.session_state.wiz_duration = duration
    st.markdown("")

    col_back, col_next = st.columns([1, 3])
    if col_back.button("← Back", use_container_width=True):
        st.session_state.wiz_step = 2
        st.rerun()
    if col_next.button("Next →", use_container_width=True):
        st.session_state.wiz_step = 4
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Severity
# ══════════════════════════════════════════════════════════════════════════════
elif step == 4:
    st.markdown("### Step 4 — How severe are your symptoms?")
    st.caption("Rate the overall intensity of your discomfort")
    st.markdown("")

    severity = st.slider(
        "Severity (1 = very mild, 5 = unbearable)",
        min_value=1, max_value=5,
        value=st.session_state.wiz_severity,
        step=1,
    )
    st.session_state.wiz_severity = severity

    # Visual severity indicator
    sev_label, sev_color = SEVERITY_LABELS[severity]
    st.markdown(
        f"<div style='background:{sev_color}22;border:1px solid {sev_color};"
        f"border-radius:8px;padding:10px 16px;margin-top:8px;"
        f"color:{sev_color};font-weight:700;font-size:15px;'>"
        f"{'●' * severity}{'○' * (5 - severity)}  {sev_label}"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown("")

    col_back, col_check = st.columns([1, 3])
    if col_back.button("← Back", use_container_width=True):
        st.session_state.wiz_step = 3
        st.rerun()
    if col_check.button("🩺 Check Symptoms", use_container_width=True, type="primary"):
        result = compute_triage(
            st.session_state.wiz_symptoms,
            st.session_state.wiz_duration,
            st.session_state.wiz_severity,
        )
        st.session_state.wiz_result = result
        st.session_state.wiz_step = 5

        # Track in analytics
        try:
            from app.analytics import track_query
            tier_map = {
                "✅ Self-care at home": "self_care",
                "🟡 See a doctor within a few days": "see_doctor",
                "🔴 Seek urgent care now": "urgent",
            }
            track_query(
                session_id="wizard",
                message=", ".join(st.session_state.wiz_symptoms),
                detected_language="en",
                category="symptom",
                triage_tier=tier_map.get(result["label"], "self_care"),
                is_emergency=(result["label"].startswith("🔴")),
            )
        except Exception:
            pass
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Result
# ══════════════════════════════════════════════════════════════════════════════
elif step == 5:
    result = st.session_state.wiz_result
    color  = result["color"]
    bg     = result["bg"]
    border = result["border"]
    icon   = result["icon"]

    # ── Triage result card ────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="background:{bg};border:2px solid {border};border-radius:12px;
                    padding:24px 28px;margin-bottom:20px;">
          <div style="font-size:36px;margin-bottom:8px;">{icon}</div>
          <div style="font-size:22px;font-weight:700;color:{color};margin-bottom:10px;">
            {result['label']}
          </div>
          <div style="font-size:14px;color:#374151;line-height:1.7;">
            {result['explanation']}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Summary of inputs ─────────────────────────────────────────────────────
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**Your symptoms:**")
        for s in st.session_state.wiz_symptoms:
            st.markdown(f"• {s.capitalize()}")
    with col_r:
        st.markdown("**Details:**")
        st.markdown(f"• Duration: {st.session_state.wiz_duration}")
        sev = st.session_state.wiz_severity
        sev_label, _ = SEVERITY_LABELS[sev]
        st.markdown(f"• Severity: {sev}/5 — {sev_label}")
        st.markdown(f"• Body area: {st.session_state.wiz_area}")

    st.divider()

    # ── Recommended actions ───────────────────────────────────────────────────
    st.markdown("### 📋 Recommended Actions")
    for action in result["actions"]:
        st.markdown(action)

    st.divider()

    # ── Emergency banner for tier 3 ───────────────────────────────────────────
    if result["label"].startswith("🔴"):
        st.error(
            "🚨 **This looks serious. Call 108 (Ambulance) or go to the nearest hospital NOW.**\n\n"
            "Do not wait or self-medicate."
        )

    # ── Disclaimer ────────────────────────────────────────────────────────────
    st.markdown(
        "<div style='background:#f7f8fa;border:1px solid #e5e7eb;border-radius:8px;"
        "padding:12px 16px;font-size:12px;color:#57606a;margin-top:8px;'>"
        "⚠️ <b>Important:</b> This is an AI-powered health <em>awareness</em> tool, "
        "not a medical diagnosis. Always consult a qualified healthcare professional "
        "for proper diagnosis and treatment."
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Action buttons ────────────────────────────────────────────────────────
    col_a, col_b, col_c = st.columns(3)

    if col_a.button("🔄 Check Again", use_container_width=True):
        for key in ["wiz_step","wiz_area","wiz_symptoms","wiz_duration","wiz_severity","wiz_result"]:
            del st.session_state[key]
        st.rerun()

    if col_b.button("🏥 Find Nearby Hospital", use_container_width=True):
        st.session_state["pending_message"] = "Nearest hospital"
        st.switch_page("streamlit_app.py")

    if col_c.button("💬 Ask Sehat Saathi", use_container_width=True):
        query = f"I have {', '.join(st.session_state.wiz_symptoms)} for {st.session_state.wiz_duration}"
        st.session_state["pending_message"] = query
        st.switch_page("streamlit_app.py")

# ── footer ─────────────────────────────────────────────────────────────────
st.markdown(
    "<hr><p style='text-align:center;color:#888;font-size:12px;'>"
    "Sehat Saathi Symptom Checker · Powered by IBM watsonx.ai + LangChain</p>",
    unsafe_allow_html=True,
)
