"""
Sehat Saathi — 🗺️ Disease Heatmap
====================================
Interactive Folium heatmap showing where health queries originate.
Clusters by category: symptom queries, vaccination, emergencies, etc.
Uses streamlit-folium to embed the map directly in Streamlit.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st

st.set_page_config(
    page_title="Sehat Saathi – Disease Map",
    page_icon="🗺️",
    layout="wide",
)

st.markdown("## 🗺️ Community Health Activity Map")
st.caption("Geographic distribution of health queries across India")
st.divider()

# ── try importing folium ─────────────────────────────────────────────────────
try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

# ── load heatmap data ────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_heatmap_data():
    try:
        from app.analytics import get_disease_heatmap_data
        return get_disease_heatmap_data()
    except Exception:
        return []


# ── category colours ─────────────────────────────────────────────────────────
CAT_COLORS = {
    "symptom": "orange",
    "vaccination": "green",
    "facility": "blue",
    "emergency": "red",
    "general": "purple",
}

CAT_ICONS = {
    "symptom": "thermometer",
    "vaccination": "tint",
    "facility": "plus-sign",
    "emergency": "warning-sign",
    "general": "info-sign",
}

CAT_LABELS = {
    "symptom": "🤒 Symptom Check",
    "vaccination": "💉 Vaccination",
    "facility": "🏥 Facility Finder",
    "emergency": "🚨 Emergency",
    "general": "💬 General",
}

# ── demo seed data (shown when no real data exists) ──────────────────────────
DEMO_POINTS = [
    {"lat": 28.6139, "lon": 77.2090, "category": "symptom",    "location": "Delhi"},
    {"lat": 28.5500, "lon": 77.3200, "category": "emergency",  "location": "Noida"},
    {"lat": 19.0760, "lon": 72.8777, "category": "vaccination","location": "Mumbai"},
    {"lat": 19.1800, "lon": 72.9700, "category": "facility",   "location": "Thane"},
    {"lat": 12.9716, "lon": 77.5946, "category": "symptom",    "location": "Bengaluru"},
    {"lat": 13.0827, "lon": 80.2707, "category": "vaccination","location": "Chennai"},
    {"lat": 22.5726, "lon": 88.3639, "category": "general",    "location": "Kolkata"},
    {"lat": 17.3850, "lon": 78.4867, "category": "symptom",    "location": "Hyderabad"},
    {"lat": 26.8467, "lon": 80.9462, "category": "emergency",  "location": "Lucknow"},
    {"lat": 25.5941, "lon": 85.1376, "category": "facility",   "location": "Patna"},
    {"lat": 23.2599, "lon": 77.4126, "category": "vaccination","location": "Bhopal"},
    {"lat": 21.1458, "lon": 79.0882, "category": "symptom",    "location": "Nagpur"},
    {"lat": 23.0225, "lon": 72.5714, "category": "general",    "location": "Ahmedabad"},
    {"lat": 26.9124, "lon": 75.7873, "category": "symptom",    "location": "Jaipur"},
    {"lat": 9.9312,  "lon": 76.2673, "category": "vaccination","location": "Kochi"},
    {"lat": 30.7333, "lon": 76.7794, "category": "facility",   "location": "Chandigarh"},
]

# ── sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔍 Filter Map")
    selected_cats = st.multiselect(
        "Categories",
        options=list(CAT_LABELS.keys()),
        default=list(CAT_LABELS.keys()),
        format_func=lambda x: CAT_LABELS.get(x, x),
    )
    show_demo = st.checkbox("Show demo data (when no real data)", value=True)
    st.divider()
    st.markdown("**Legend**")
    for cat, color in CAT_COLORS.items():
        label = CAT_LABELS.get(cat, cat)
        st.markdown(f"🔴" if color == "red" else
                    f"🟠" if color == "orange" else
                    f"🟢" if color == "green" else
                    f"🔵" if color == "blue" else
                    f"🟣" + f" {label}")

# ── load real data ────────────────────────────────────────────────────────────
real_data = load_heatmap_data()
points = real_data if real_data else (DEMO_POINTS if show_demo else [])

# Filter by selected categories
points = [p for p in points if p.get("category", "general") in selected_cats]

# ── counts summary ────────────────────────────────────────────────────────────
total_points = len(points)
using_demo = not real_data and show_demo

if using_demo:
    st.info("📍 Showing **demo data** — location-tagged queries will appear here once users provide their location.")
else:
    st.success(f"📍 Showing **{total_points} real location-tagged queries** from your Sehat Saathi deployment.")

# category counts
from collections import Counter
cat_counts = Counter(p.get("category", "general") for p in points)
cols = st.columns(len(CAT_LABELS))
for i, (cat, label) in enumerate(CAT_LABELS.items()):
    cols[i].metric(label, cat_counts.get(cat, 0))

st.divider()

# ── render map ────────────────────────────────────────────────────────────────
if not FOLIUM_AVAILABLE:
    st.warning(
        "📦 `folium` and `streamlit-folium` are not installed.\n\n"
        "Run: `pip install folium streamlit-folium`"
    )
    st.markdown("### 📋 Query Locations (Table View)")
    if points:
        import pandas as pd
        # Normalise: ensure every point has the same keys before building DataFrame
        normalised = [
            {
                "location": p.get("location", ""),
                "category": p.get("category", "general"),
                "date":     p.get("date", "—"),
            }
            for p in points
        ]
        df = pd.DataFrame(normalised)
        df["Category"] = df["category"].map(CAT_LABELS)
        st.dataframe(
            df[["location", "Category", "date"]].rename(columns={
                "location": "Location", "date": "Date"
            }),
            use_container_width=True,
        )
    else:
        st.info("No location data to display.")
else:
    # Build Folium map centred on India
    m = folium.Map(
        location=[20.5937, 78.9629],
        zoom_start=5,
        tiles="CartoDB positron",
    )

    # Add markers
    for point in points:
        cat = point.get("category", "general")
        color = CAT_COLORS.get(cat, "gray")
        icon_name = CAT_ICONS.get(cat, "info-sign")
        label = CAT_LABELS.get(cat, cat)
        loc_name = point.get("location", "Unknown")
        date_str = point.get("date", "")

        popup_html = f"""
        <div style="font-family:sans-serif;min-width:160px;">
          <b>{loc_name}</b><br>
          <span style="color:{color}">{label}</span><br>
          <small>{date_str}</small>
        </div>
        """
        folium.Marker(
            location=[point["lat"], point["lon"]],
            popup=folium.Popup(popup_html, max_width=200),
            tooltip=f"{loc_name} — {label}",
            icon=folium.Icon(color=color, icon=icon_name, prefix="glyphicon"),
        ).add_to(m)

    # Render
    map_result = st_folium(m, width="100%", height=520, returned_objects=[])

# ── data note ─────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    "**How location data is collected:** When a user asks for nearby facilities "
    "or mentions their city/pincode in a query, Sehat Saathi logs the location "
    "tag alongside the query category. No personal data is stored — only the "
    "city-level location is recorded."
)

# ── refresh ───────────────────────────────────────────────────────────────────
if st.button("🔄 Refresh Map"):
    st.cache_data.clear()
    st.rerun()

st.markdown(
    "<hr><p style='text-align:center;color:#888;font-size:12px;'>"
    "Sehat Saathi Health Map · Powered by IBM watsonx.ai + LangChain</p>",
    unsafe_allow_html=True,
)
