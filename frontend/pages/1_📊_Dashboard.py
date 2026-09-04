"""
Sehat Saathi — 📊 Analytics Dashboard
======================================
Streamlit multipage — shows real-time usage analytics pulled from
the FastAPI /analytics endpoint (or directly from app.analytics).
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import pandas as pd
from datetime import datetime

# ── page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sehat Saathi – Dashboard",
    page_icon="📊",
    layout="wide",
)

# ── load analytics ───────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_summary():
    try:
        from app.analytics import get_summary
        return get_summary()
    except Exception as e:
        return None


# ── language display names ───────────────────────────────────────────────────
LANG_NAMES = {
    "en": "English", "hi": "Hindi", "kn": "Kannada",
    "ta": "Tamil", "te": "Telugu", "bn": "Bengali",
    "mr": "Marathi", "gu": "Gujarati", "pa": "Punjabi", "ml": "Malayalam",
}

CAT_LABELS = {
    "symptom": "🤒 Symptom Check",
    "vaccination": "💉 Vaccination",
    "facility": "🏥 Facility Finder",
    "emergency": "🚨 Emergency",
    "general": "💬 General Query",
}

TRIAGE_LABELS = {
    "self_care": "🟢 Self-care at Home",
    "see_doctor": "🟡 See a Doctor",
    "urgent": "🔴 Urgent Care",
    None: "—",
    "None": "—",
}

# ── header ───────────────────────────────────────────────────────────────────
st.markdown("## 📊 Sehat Saathi — Usage Dashboard")
st.caption(f"Live analytics · Last refreshed: {datetime.now().strftime('%H:%M:%S')}")
st.divider()

summary = load_summary()

if summary is None:
    st.error("Could not load analytics. Make sure the backend is running.")
    st.stop()

# ── KPI row ──────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Queries", f"{summary['total_queries']:,}")
k2.metric("Unique Sessions", f"{summary['unique_sessions']:,}")
k3.metric("Today's Queries", f"{summary['today_count']:,}")
k4.metric("🚨 Emergency Alerts", f"{summary['emergency_alerts']:,}",
          delta=f"Today: {summary['today_emergencies']}" if summary['today_emergencies'] else None,
          delta_color="inverse")

st.divider()

# ── charts row ───────────────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📅 Daily Query Trend (Last 14 Days)")
    trend = summary.get("daily_trend", {})
    dates = trend.get("dates", [])
    counts = trend.get("counts", [])
    if dates:
        df_trend = pd.DataFrame({"Date": dates, "Queries": counts})
        df_trend["Date"] = pd.to_datetime(df_trend["Date"])
        st.line_chart(df_trend.set_index("Date"), height=250)
    else:
        st.info("No trend data yet. Start chatting to generate data!")

with col_right:
    st.subheader("🌐 Language Distribution")
    lang_dist = summary.get("language_distribution", {})
    if lang_dist:
        df_lang = pd.DataFrame([
            {"Language": LANG_NAMES.get(k, k), "Queries": v}
            for k, v in lang_dist.items()
        ]).sort_values("Queries", ascending=False)
        st.bar_chart(df_lang.set_index("Language"), height=250)
    else:
        st.info("No language data yet.")

# ── second row ───────────────────────────────────────────────────────────────
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("🗂️ Query Categories")
    cat_dist = summary.get("category_distribution", {})
    if cat_dist:
        df_cat = pd.DataFrame([
            {"Category": CAT_LABELS.get(k, k), "Count": v}
            for k, v in cat_dist.items()
        ]).sort_values("Count", ascending=False)
        st.bar_chart(df_cat.set_index("Category"), height=220)
    else:
        st.info("No category data yet.")

with col_b:
    st.subheader("🏥 Triage Tier Breakdown")
    triage_dist = summary.get("triage_distribution", {})
    if triage_dist:
        df_triage = pd.DataFrame([
            {"Tier": TRIAGE_LABELS.get(k, k), "Count": v}
            for k, v in triage_dist.items()
            if k and k != "None" and v > 0
        ])
        if not df_triage.empty:
            st.bar_chart(df_triage.set_index("Tier"), height=220)
        else:
            st.info("No triage data yet.")
    else:
        st.info("No triage data yet.")

st.divider()

# ── impact summary ───────────────────────────────────────────────────────────
st.subheader("🌍 Community Impact")
total = summary["total_queries"]
emergency = summary["emergency_alerts"]
if total > 0:
    pct_emergency = (emergency / total) * 100
    languages_used = len(summary.get("language_distribution", {}))
    st.markdown(
        f"""
        <div style="background:#f0fdf4;border-left:4px solid #22c55e;padding:16px;border-radius:8px;">
        <b>Sehat Saathi has handled <span style="color:#16a34a">{total:,} health queries</span>
        across <span style="color:#16a34a">{summary['unique_sessions']:,} unique users</span>
        in <span style="color:#16a34a">{languages_used} languages</span>.</b><br>
        🚨 Emergency referrals: <b>{emergency}</b> ({pct_emergency:.1f}% of total)<br>
        📅 Active today: <b>{summary['today_count']}</b> queries
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.info("No queries tracked yet. Start a conversation on the main Chat page!")

# ── refresh button ───────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
if st.button("🔄 Refresh Dashboard"):
    st.cache_data.clear()
    st.rerun()

# ── footer ───────────────────────────────────────────────────────────────────
st.markdown(
    "<hr><p style='text-align:center;color:#888;font-size:12px;'>"
    "Sehat Saathi Analytics · Powered by IBM watsonx.ai + LangChain</p>",
    unsafe_allow_html=True,
)
