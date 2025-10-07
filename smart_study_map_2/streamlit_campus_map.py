import streamlit as st
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Campus Map", layout="wide")
st.title("Campus map (live Leaflet via Folium)")

# Center: SRM KTR (example); change to your campus coords
CENTER = (12.8230, 80.0450)

m = folium.Map(location=CENTER, zoom_start=15, tiles="OpenStreetMap")
folium.Marker(CENTER, tooltip="Campus Center", popup="SRM KTR").add_to(m)

# Example: add more points dynamically (replace with your data source)
rooms = [
    {"name": "Library", "lat": 12.8217, "lng": 80.0419},
    {"name": "Admin Block", "lat": 12.8236, "lng": 80.0475},
]
for r in rooms:
    folium.Marker([r["lat"], r["lng"]], tooltip=r["name"]).add_to(m)

st_folium(m, width=None, height=600)
