"""
streamlit_admin/admin.py

Admin dashboard (updated):
- Derive status where "Booked" and "Full" are considered the same -> "Full"
- Inline occupancy reporting for visible rooms
- Configurable number of rows shown
- Analytics (pie + bar) and map (rebuild on demand)
- POSTs JSON {"occupancy_level": <int>} to /rooms/{room_id}/checkin
"""

from datetime import datetime, timezone
import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Optional libraries
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY = True
except Exception:
    PLOTLY = False

try:
    import folium
    FOLIUM = True
except Exception:
    FOLIUM = False

st.set_page_config(page_title="Smart Study Map — Admin", layout="wide")
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
st.title("🏫 Smart Study Map — Admin (Occupancy Reporting)")

# ---------------- thresholds (tweakable) ----------------
FULL_THRESHOLD = 95      # occupancy % >= this -> "Full" (includes backend 'Booked')
PARTIAL_THRESHOLD = 30   # occupancy % > this -> "Partial"

# ---------------- Sidebar / Controls ----------------
API_BASE = st.sidebar.text_input("API Base URL", value="http://127.0.0.1:8000")
st.sidebar.markdown("---")
refresh_data_btn = st.sidebar.button("🔄 Refresh Data (table & analytics)")
rebuild_map_btn = st.sidebar.button("🗺️ Rebuild Map (re-generate map HTML)")
rows_to_show = st.sidebar.slider("Rows to show in table", min_value=5, max_value=50, value=15, step=1,
                                 help="How many room rows to display in the quick table.")
st.sidebar.markdown("---")
st.sidebar.caption("Note: 'Full' includes both occupancy-derived full rooms and timetable-booked rooms.")

# session cache for map HTML
if "map_html" not in st.session_state:
    st.session_state["map_html"] = None

# ---------------- Data helpers ----------------
@st.cache_data(ttl=20)
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

@st.cache_data(ttl=20)
def fetch_heatmap(api_base: str) -> pd.DataFrame:
    try:
        r = requests.get(f"{api_base.rstrip('/')}/analytics/heatmap", timeout=8)
        r.raise_for_status()
        return pd.DataFrame(r.json())
    except Exception:
        return pd.DataFrame()

# manual cache clear
if refresh_data_btn:
    fetch_rooms.clear()
    fetch_heatmap.clear()
    st.success("Data caches cleared — table and analytics will refresh.")

rooms_df = fetch_rooms(API_BASE)
heat_df = fetch_heatmap(API_BASE)

# ---------------- derive status: merge 'Booked' and Full ----------------
def derive_status_from_row(row):
    """
    Priority:
      1) If backend provided status contains 'Booked' -> Full
      2) Else if occupancy_level >= FULL_THRESHOLD -> Full
      3) Else if occupancy_level > PARTIAL_THRESHOLD -> Partial
      4) Else -> Free
    Returns: one of "Free", "Partial", "Full"
    """
    backend_status = str(row.get('status', '') or '')
    lvl = int(row.get('occupancy_level', 0) or 0)

    if "Booked" in backend_status:
        return "Full"
    if lvl >= FULL_THRESHOLD:
        return "Full"
    if lvl > PARTIAL_THRESHOLD:
        return "Partial"
    return "Free"

# ---------------- Top metrics ----------------
c1, c2, c3, c4 = st.columns([1.2, 1.0, 1.0, 1.4])
c1.metric("Total rooms", len(rooms_df))
c2.metric("Free now", int(rooms_df.apply(lambda r: derive_status_from_row(r) == "Free", axis=1).sum()) if not rooms_df.empty else 0)
c3.metric("Avg occupancy %", int(rooms_df['occupancy_level'].mean()) if not rooms_df.empty else 0)
c4.metric("Last refresh (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

st.markdown("---")

# ---------------- CSV upload ----------------
with st.expander("📤 Upload CSVs to populate DB (rooms.csv + timetable.csv)"):
    st.write("Upload both CSV files and click Upload. This writes temporary files to project root and calls backend /admin/load_csv.")
    rooms_file = st.file_uploader("rooms.csv", type=["csv"])
    tt_file = st.file_uploader("timetable.csv", type=["csv"])
    if st.button("Upload & Populate DB"):
        if not rooms_file or not tt_file:
            st.error("Please upload both CSV files.")
        else:
            tmp_rooms = "tmp_admin_rooms.csv"
            tmp_tt = "tmp_admin_timetable.csv"
            with open(tmp_rooms, "wb") as f:
                f.write(rooms_file.getbuffer())
            with open(tmp_tt, "wb") as f:
                f.write(tt_file.getbuffer())
            try:
                resp = requests.post(f"{API_BASE.rstrip('/')}/admin/load_csv",
                                     data={"rooms_path": tmp_rooms, "timetable_path": tmp_tt},
                                     timeout=30)
                if resp.status_code == 200:
                    st.success("CSV load requested. Database population triggered.")
                    fetch_rooms.clear()
                else:
                    st.error(f"Backend error: {resp.status_code} {resp.text}")
            except Exception as e:
                st.error(f"Network error: {e}")

st.markdown("---")

# ---------------- Main layout ----------------
left, right = st.columns([2.6, 1.4])

with left:
    st.subheader("Rooms — quick actions & occupancy reporting")

    if rooms_df.empty:
        st.info("No rooms available. Start backend and populate DB.")
    else:
        blocks = ["All"] + sorted(rooms_df['block'].dropna().unique().tolist())
        sel_block = st.selectbox("Filter by block", options=blocks, index=0)
        sel_status = st.selectbox("Filter by status", options=["All", "Free", "Partial", "Full"], index=0)
        min_cap = st.number_input("Min capacity", min_value=0, value=0)

        q = rooms_df.copy()
        if sel_block != "All":
            q = q[q['block'] == sel_block]
        if sel_status != "All":
            q = q[q.apply(lambda r: derive_status_from_row(r) == sel_status, axis=1)]
        if min_cap:
            q = q[q['capacity'] >= int(min_cap)]

        total_matches = len(q)
        st.write(f"Showing {min(total_matches, rows_to_show)} of {total_matches} matching rooms (top rows).")

        # header
        hdr = st.columns([2,1,1,1,1,1])
        hdr[0].markdown("**Room**")
        hdr[1].markdown("**Block**")
        hdr[2].markdown("**Capacity**")
        hdr[3].markdown("**Last occ (%)**")
        hdr[4].markdown("**Status**")
        hdr[5].markdown("**Report occupancy**")

        display_df = q.head(rows_to_show)
        for _, row in display_df.iterrows():
            c_room, c_block, c_cap, c_occ, c_status, c_action = st.columns([2,1,1,1,1,1])
            c_room.write(f"**{row['room_id']}**")
            c_block.write(row.get('block', '—'))
            c_cap.write(row.get('capacity', '—'))
            c_occ.write(int(row.get('occupancy_level', 0)))

            status_val = derive_status_from_row(row)
            if status_val == "Free":
                c_status.success("Free")
            elif status_val == "Partial":
                c_status.warning("Partial")
            else:  # Full
                c_status.error("Full")

            # Inline report: numeric input + Report button
            slider_key = f"occ_slider_{row['room_id']}"
            btn_key = f"occ_btn_{row['room_id']}"
            default_val = int(row.get('occupancy_level', 10))
            occ_val = c_action.number_input("%", min_value=0, max_value=100, value=default_val, key=slider_key, step=1, format="%d")
            if c_action.button("Report", key=btn_key):
                try:
                    payload = {"occupancy_level": int(occ_val)}
                    resp = requests.post(f"{API_BASE.rstrip('/')}/rooms/{row['room_id']}/checkin", json=payload, timeout=8)
                    if resp.status_code == 200:
                        st.success(f"Reported {int(occ_val)}% for {row['room_id']}")
                        fetch_rooms.clear()
                    else:
                        st.error(f"Failed to report: {resp.status_code} {resp.text}")
                except Exception as e:
                    st.error(f"Network error while reporting: {e}")

with right:
    st.subheader("Analytics & Map")

    # status distribution (Free / Partial / Full)
    if not rooms_df.empty:
        rooms_df['status_short'] = rooms_df.apply(derive_status_from_row, axis=1)
        status_counts = rooms_df['status_short'].value_counts().reindex(["Free", "Partial", "Full"], fill_value=0)

        if PLOTLY:
            pie_fig = go.Figure(data=[go.Pie(labels=status_counts.index.tolist(), values=status_counts.values.tolist(), hole=0.35)])
            pie_fig.update_layout(margin=dict(l=10, r=10, t=20, b=10), title_text="Room status distribution")
            st.plotly_chart(pie_fig, use_container_width=True)
        else:
            st.write(status_counts.to_frame(name="count"))

    # avg occupancy by block
    if not heat_df.empty:
        bar_df = heat_df.sort_values("avg_occupancy", ascending=False)
    else:
        bar_df = rooms_df.groupby('block', dropna=False)['occupancy_level'].mean().reset_index().rename(columns={'occupancy_level': 'avg_occupancy'})
        bar_df = bar_df.sort_values("avg_occupancy", ascending=False)

    if not bar_df.empty:
        if PLOTLY:
            fig_bar = px.bar(bar_df, x='block', y='avg_occupancy', labels={'avg_occupancy': 'Avg occupancy (%)', 'block': 'Block'}, title="Avg occupancy by block")
            fig_bar.update_layout(margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.bar_chart(bar_df.set_index('block')['avg_occupancy'])

    st.markdown("---")
    st.subheader("Campus map (static — rebuild on demand)")

    def build_map_html(df):
        mdf = df[['lat', 'lon', 'room_id', 'status', 'occupancy_level']].dropna().head(1000)
        if mdf.empty:
            return "<div>No geolocated rooms</div>"
        center = [float(mdf['lat'].mean()), float(mdf['lon'].mean())]
        import folium as _folium
        m = _folium.Map(location=center, zoom_start=15)
        for _, r in mdf.iterrows():
            s = derive_status_from_row(r)
            color = "#16a34a" if s == "Free" else ("#f97316" if s == "Partial" else "#ef4444")
            popup = _folium.Popup(f"{r['room_id']}<br>{s}<br>Occ: {r['occupancy_level']}%", max_width=260)
            _folium.CircleMarker(location=[r['lat'], r['lon']], radius=6, color=color, fill=True, popup=popup).add_to(m)
        return m.get_root().render()

    if rebuild_map_btn or st.session_state["map_html"] is None:
        if FOLIUM:
            try:
                st.session_state["map_html"] = build_map_html(rooms_df)
                st.success("Map rebuilt and cached.")
            except Exception as e:
                st.error(f"Failed to build map: {e}")
                st.session_state["map_html"] = None
        else:
            st.info("Install folium (`pip install folium`) to enable map rendering.")

    if st.session_state.get("map_html"):
        components.html(st.session_state["map_html"], height=520, scrolling=True)
    else:
        st.info("No map HTML cached. Click 'Rebuild Map' to create it.")

st.markdown("---")
st.caption("Admin dashboard. Add authentication & audit logging before production use.")