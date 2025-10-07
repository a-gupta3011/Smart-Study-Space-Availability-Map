"""
streamlit_user/user.py

User-facing Streamlit UI (updated):
- Derive status where "Booked" merges into "Full"
- "Full" rooms cannot be checked in
- "Partial" and "Free" are available; changeable thresholds
- Map of nearest rooms; inline check-in button for Free rooms
"""

import math
from datetime import datetime, timezone
import requests
import pandas as pd
import streamlit as st

# Optional map libs
try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM = True
except Exception:
    FOLIUM = False

st.set_page_config(page_title="Smart Study Map — User", layout="wide")
# Lightweight aesthetic theme for Streamlit
st.markdown(
    """
    <style>
      .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
      .stButton>button {background: linear-gradient(180deg,#1a3d86,#15326d); border: 1px solid #254987; color: #fff; border-radius: 10px; padding: 8px 14px}
      .stButton>button:disabled {opacity: .6}
      .stMetric {background: rgba(16,24,48,.5); border: 1px solid #223059; border-radius: 12px; padding: 10px}
      .stSelectbox, .stNumberInput, .stTextInput {border-radius: 10px}
      .stDataFrame, .stTable {border: 1px solid #223059; border-radius: 12px}
      .stAlert {border-radius: 12px}
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("🔎 Find a study spot — User")

# ---------------- thresholds (tweakable) ----------------
FULL_THRESHOLD = 95      # occupancy % >= this -> Full (includes backend 'Booked')
PARTIAL_THRESHOLD = 30   # occupancy % > this -> Partial

# Sidebar controls
API_BASE = st.sidebar.text_input("API Base URL", "http://127.0.0.1:8000")
st.sidebar.markdown("---")
LOC_PRESET = st.sidebar.selectbox("Your location", ["Center campus", "Block A", "Block B", "Custom"])
MAX_RESULTS = st.sidebar.slider("Max results", 5, 50, 10)
MAP_ZOOM = st.sidebar.slider("Map zoom", 12, 18, 15)
REFRESH = st.sidebar.button("🔄 Refresh Data")

# ---------------- Data fetcher ----------------
@st.cache_data(ttl=30)
def fetch_rooms(api_base: str) -> pd.DataFrame:
    try:
        r = requests.get(f"{api_base.rstrip('/')}/rooms/all", timeout=8)
        r.raise_for_status()
        df = pd.DataFrame(r.json())
        if not df.empty:
            df['occupancy_level'] = pd.to_numeric(df.get('occupancy_level', 0), errors='coerce').fillna(0).astype(int)
            df['lat'] = pd.to_numeric(df.get('lat'), errors='coerce')
            df['lon'] = pd.to_numeric(df.get('lon'), errors='coerce')
            df['block'] = df.get('block').fillna("Unknown")
        return df
    except Exception as e:
        st.error(f"Failed to fetch rooms: {e}")
        return pd.DataFrame()

if REFRESH:
    fetch_rooms.clear()

rooms_df = fetch_rooms(API_BASE)
if rooms_df.empty:
    st.warning("No room data available. Start backend and populate DB.")
    st.stop()

# ---------------- Location selection ----------------
if LOC_PRESET == "Center campus":
    my_lat = float(rooms_df['lat'].mean())
    my_lon = float(rooms_df['lon'].mean())
elif LOC_PRESET == "Block A":
    my_lat, my_lon = 12.900, 80.100
elif LOC_PRESET == "Block B":
    my_lat, my_lon = 12.930, 80.130
else:
    my_lat = st.sidebar.number_input("Latitude", value=float(rooms_df['lat'].mean()))
    my_lon = st.sidebar.number_input("Longitude", value=float(rooms_df['lon'].mean()))

# ---------------- utilities ----------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1); phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1); dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(dlambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# compute distances
rooms_df['distance_m'] = rooms_df.apply(lambda r: haversine(my_lat, my_lon, r['lat'], r['lon']) if pd.notnull(r['lat']) and pd.notnull(r['lon']) else 1e9, axis=1)

# ---------------- derive status (Booked merged into Full) ----------------
def derive_status_from_row(row):
    backend_status = str(row.get('status', '') or '')
    lvl = int(row.get('occupancy_level', 0) or 0)
    if "Booked" in backend_status:
        return "Full"
    if lvl >= FULL_THRESHOLD:
        return "Full"
    if lvl > PARTIAL_THRESHOLD:
        return "Partial"
    return "Free"

# ---------------- Top controls ----------------
col_q, col_block, col_cap, col_sort = st.columns([3,1,1,1])
with col_q:
    query = st.text_input("Search (room id or amenity)", placeholder="e.g. R101, projector")
with col_block:
    block_filter = st.selectbox("Block", options=["All"] + sorted(rooms_df['block'].unique().tolist()))
with col_cap:
    min_capacity = st.number_input("Min capacity", min_value=0, value=0)
with col_sort:
    sort_by = st.selectbox("Sort by", options=["distance", "capacity", "occupancy"])

# filtering
filtered = rooms_df.copy()
if block_filter != "All":
    filtered = filtered[filtered['block'] == block_filter]
if min_capacity:
    filtered = filtered[filtered['capacity'] >= int(min_capacity)]
if query:
    ql = query.lower()
    filtered = filtered[filtered.apply(lambda r: ql in str(r['room_id']).lower() or ql in str(r.get('amenities','')).lower(), axis=1)]

# sorting
if sort_by == "distance":
    filtered = filtered.sort_values("distance_m")
elif sort_by == "capacity":
    filtered = filtered.sort_values("capacity", ascending=False)
else:
    filtered = filtered.sort_values("occupancy_level")

nearest = filtered.head(int(MAX_RESULTS))

# ---------------- Metrics ----------------
m1, m2, m3 = st.columns(3)
m1.metric("Total rooms", len(rooms_df))
m2.metric("Free now", int(rooms_df.apply(lambda r: derive_status_from_row(r) == "Free", axis=1).sum()))
m3.metric("Avg occupancy %", int(rooms_df['occupancy_level'].mean()))

st.markdown("---")

# ---------------- Layout: list + map ----------------
left, right = st.columns([1.2, 1])

with left:
    st.subheader("Top matched rooms")
    if nearest.empty:
        st.info("No rooms match your filters.")
    else:
        for _, row in nearest.iterrows():
            c1, c2, c3 = st.columns([3,1,1])
            with c1:
                st.markdown(f"**{row['room_id']}** — {row.get('block','—')} • {row.get('capacity',0)} seats")
                if row.get('amenities'):
                    st.caption(f"{row['amenities']}")
                st.write(f"Status: **{derive_status_from_row(row)}** — Occupancy: **{int(row.get('occupancy_level',0))}%**")
            with c2:
                st.write(f"**{int(row['distance_m'])} m**")
            with c3:
                status_now = derive_status_from_row(row)
                # allow check-in for Free or Partial (change if you want only Free)
                if status_now == "Free" or status_now == "Partial":
                    # if you prefer Partial to be non-checkin, remove it above
                    if st.button("Check-in", key=f"ci_{row['room_id']}"):
                        try:
                            payload = {"occupancy_level": 1}
                            resp = requests.post(f"{API_BASE.rstrip('/')}/rooms/{row['room_id']}/checkin", json=payload, timeout=8)
                            if resp.status_code == 200:
                                st.success(f"Checked in to {row['room_id']}")
                                fetch_rooms.clear()
                            else:
                                st.error(f"Failed to check-in: {resp.status_code} {resp.text}")
                        except Exception as e:
                            st.error(f"Network error: {e}")
                else:
                    st.button("Unavailable", key=f"na_{row['room_id']}", disabled=True)

with right:
    st.subheader("Map")
    if FOLIUM and not nearest.empty:
        center = [my_lat, my_lon]
        m = folium.Map(location=center, zoom_start=15)
        folium.Marker(location=center, popup="You (approx)", icon=folium.Icon(color="blue")).add_to(m)
        for _, rr in nearest.iterrows():
            st_status = derive_status_from_row(rr)
            color = "green" if st_status == "Free" else ("orange" if st_status == "Partial" else "red")
            folium.CircleMarker(location=[rr['lat'], rr['lon']], radius=6, color=color, fill=True,
                                popup=f"{rr['room_id']} — {st_status} — {int(rr['occupancy_level'])}%").add_to(m)
        st_folium(m, width=700, height=560)
    else:
        try:
            st.map(nearest[['lat','lon']].rename(columns={'lat':'latitude','lon':'longitude'}).dropna())
        except Exception:
            st.info("Install folium & streamlit_folium for a richer map view.")

st.markdown("---")
st.caption(f"Data last refreshed: {datetime.now(timezone.utc).isoformat()} UTC")