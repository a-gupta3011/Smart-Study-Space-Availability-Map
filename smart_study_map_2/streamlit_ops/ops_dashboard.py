from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import statistics
import numpy as np
import pandas as pd

import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests

# Optional plotting
try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY = True
except Exception:
    PLOTLY = False

# Ensure project root is first on sys.path so we import the top-level 'ops' package,
# not the local streamlit_ops/ops.py module.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ops.health_monitor import probe_health, append_probe, read_window, compute_metrics

st.set_page_config(
    page_title="Backend Operations Dashboard",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced CSS for better styling and spacing
st.markdown("""
<style>
/* Main container styling */
.main .block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1400px;
}

/* Metric cards styling */
.metric-container {
    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    padding: 1.5rem;
    border-radius: 15px;
    border-left: 5px solid #4CAF50;
    margin: 0.8rem 0;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    transition: transform 0.2s ease-in-out;
}

.metric-container:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 15px rgba(0, 0, 0, 0.15);
}

/* Status styling */
.status-up {
    color: #28a745;
    font-weight: bold;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.status-down {
    color: #dc3545;
    font-weight: bold;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.status-unknown {
    color: #ffc107;
    font-weight: bold;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

/* Alert boxes with improved spacing */
.alert-box {
    padding: 1.2rem;
    border-radius: 12px;
    margin: 1.5rem 0;
    border: 2px solid;
    font-weight: 500;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    animation: fadeIn 0.5s ease-in;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(-10px); }
    to { opacity: 1; transform: translateY(0); }
}

.alert-success {
    background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
    color: #155724;
    border-color: #c3e6cb;
}

.alert-danger {
    background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
    color: #721c24;
    border-color: #f5c6cb;
}

.alert-warning {
    background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
    color: #856404;
    border-color: #ffeaa7;
}

/* Section headers */
.section-header {
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 1rem 1.5rem;
    border-radius: 10px;
    margin: 2rem 0 1rem 0;
    text-align: center;
    font-weight: 600;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
}

/* Chart containers */
.chart-container {
    background: white;
    border-radius: 15px;
    padding: 1.5rem;
    margin: 1.5rem 0;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.1);
    border: 1px solid #e1e5e9;
}

/* Sidebar enhancements */
.css-1d391kg {
    background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
}

/* Spacing utilities */
.spacing-sm { margin: 0.5rem 0; }
.spacing-md { margin: 1rem 0; }
.spacing-lg { margin: 2rem 0; }
.spacing-xl { margin: 3rem 0; }

/* Column gaps */
.stColumn > div { padding: 0 0.75rem; }

/* Metric value styling */
[data-testid="metric-container"] {
    background: rgba(255, 255, 255, 0.8);
    border: 1px solid #dee2e6;
    padding: 1rem;
    border-radius: 8px;
    margin: 0.5rem 0;
}

/* Plotly chart margins */
.js-plotly-plot {
    margin: 1rem 0 !important;
}

/* Section dividers */
.section-divider {
    border: none;
    height: 3px;
    background: linear-gradient(90deg, transparent, #667eea, transparent);
    margin: 3rem 0;
}

</style>
""", unsafe_allow_html=True)

st.title("🛠️ Backend Operations Dashboard")
st.markdown("### 📊 Live Health & Performance Metrics")

# Enhanced Sidebar
st.sidebar.header("🔧 Configuration")
with st.sidebar.expander("🎯 API Settings", expanded=True):
    API_BASE = st.text_input("API Base URL", value="http://127.0.0.1:8000")
    PROBE_TIMEOUT = st.slider("Probe timeout (seconds)", min_value=1, max_value=10, value=3)

with st.sidebar.expander("🔄 Monitoring Settings", expanded=True):
    AUTO_PROBE = st.checkbox("Auto probe on refresh", value=True)
    REFRESH_SEC = st.slider("Auto-refresh (seconds)", min_value=2, max_value=60, value=5)
    WINDOW_MIN = st.slider("Metrics window (minutes)", min_value=5, max_value=240, value=60)

with st.sidebar.expander("📊 Display Options", expanded=False):
    SHOW_RAW_DATA = st.checkbox("Show raw data table", value=False)
    CHART_HEIGHT = st.slider("Chart height (px)", min_value=200, max_value=600, value=400)
    ENABLE_ALERTS = st.checkbox("Enable status alerts", value=True)

# Auto-refresh trigger
if REFRESH_SEC and REFRESH_SEC > 0:
    st_autorefresh(interval=REFRESH_SEC * 1000, key="ops_autorefresh")

# Perform a probe each run if enabled
if AUTO_PROBE:
    res = probe_health(API_BASE, timeout=float(PROBE_TIMEOUT))
    append_probe(res)
else:
    if st.sidebar.button("Probe now"):
        res = probe_health(API_BASE, timeout=float(PROBE_TIMEOUT))
        append_probe(res)

# Load recent data
rows = read_window(WINDOW_MIN)

# Compute metrics
uptime_pct, avg_latency, errors_count, last_down_at = compute_metrics(rows)

# Enhanced Metrics Calculation
current_status = rows[-1]["status"] if rows else "unknown"
current_latency = rows[-1]["latency_ms"] if rows and rows[-1]["latency_ms"] is not None else None

# Calculate additional metrics
if rows:
    # Response time statistics
    valid_latencies = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
    if valid_latencies:
        min_latency = min(valid_latencies)
        max_latency = max(valid_latencies)
        p95_latency = np.percentile(valid_latencies, 95) if len(valid_latencies) > 1 else valid_latencies[0]
        std_latency = statistics.stdev(valid_latencies) if len(valid_latencies) > 1 else 0
    else:
        min_latency = max_latency = p95_latency = std_latency = None
    
    # Availability metrics
    recent_5min = [r for r in rows if r["timestamp"] > (datetime.now(timezone.utc) - timedelta(minutes=5))]
    recent_uptime = (sum(1 for r in recent_5min if r["status"] == "up") / len(recent_5min) * 100) if recent_5min else 0
    
    # Error rate
    total_requests = len(rows)
    error_rate = (errors_count / total_requests * 100) if total_requests > 0 else 0
else:
    min_latency = max_latency = p95_latency = std_latency = None
    recent_uptime = error_rate = 0
    total_requests = 0

# Status Alert Section with proper spacing
st.markdown('<div class="spacing-md"></div>', unsafe_allow_html=True)
if ENABLE_ALERTS:
    if current_status == "down":
        st.markdown('<div class="alert-box alert-danger">⚠️ <strong>CRITICAL ALERT:</strong> Backend service is currently DOWN!</div>', unsafe_allow_html=True)
    elif recent_uptime < 95 and recent_uptime > 0:
        st.markdown('<div class="alert-box alert-warning">⚠️ <strong>WARNING:</strong> Service availability has dropped below 95% in the last 5 minutes</div>', unsafe_allow_html=True)
    elif current_status == "up":
        st.markdown('<div class="alert-box alert-success">✅ <strong>SYSTEM HEALTHY:</strong> All systems operational</div>', unsafe_allow_html=True)

# Section Divider
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

# Enhanced Metrics Dashboard Header
st.markdown('<div class="section-header">📈 System Health Overview</div>', unsafe_allow_html=True)
st.markdown('<div class="spacing-sm"></div>', unsafe_allow_html=True)

# Primary Metrics Row with Container
with st.container():
    col1, col2, col3, col4, col5 = st.columns(5, gap="medium")
    
    with col1:
        status_label = "🟢 Live" if current_status == "up" else ("🔴 Down" if current_status == "down" else "⚪ Unknown")
        st.metric(
            label="🖥️ Server Status", 
            value=status_label,
            help="Current backend service status"
        )
        
    with col2:
        if current_latency is not None:
            delta_val = f"{current_latency - avg_latency:.0f} ms" if avg_latency else None
            st.metric(
                label="⏱️ Current Latency", 
                value=f"{current_latency:.0f} ms",
                delta=delta_val,
                help="Latest response time measurement"
            )
        else:
            st.metric(
                label="⏱️ Current Latency", 
                value="—",
                help="No recent latency data available"
            )
            
    with col3:
        delta_val = f"{recent_uptime - uptime_pct:.1f}%" if recent_uptime != uptime_pct else None
        st.metric(
            label="📈 Uptime (Window)", 
            value=f"{uptime_pct:.2f}%",
            delta=delta_val,
            help=f"Service availability over {WINDOW_MIN} minutes"
        )
                 
    with col4:
        st.metric(
            label="⚠️ Error Rate", 
            value=f"{error_rate:.2f}%",
            delta=f"{errors_count} errors",
            delta_color="inverse",
            help="Percentage of failed requests"
        )
                 
    with col5:
        st.metric(
            label="📋 Total Requests", 
            value=f"{total_requests:,}",
            help=f"Total probes in {WINDOW_MIN} minute window"
        )

# Spacing between sections
st.markdown('<div class="spacing-lg"></div>', unsafe_allow_html=True)

# Secondary Metrics Row (Response Time Analytics)
if valid_latencies:
    st.markdown('<div class="section-header">📊 Response Time Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="spacing-sm"></div>', unsafe_allow_html=True)
    
    with st.container():
        col1, col2, col3, col4 = st.columns(4, gap="medium")
        
        with col1:
            st.metric(
                label="⬇️ Min Latency", 
                value=f"{min_latency:.0f} ms" if min_latency else "—",
                help="Minimum response time in window"
            )
        with col2:
            st.metric(
                label="⬆️ Max Latency", 
                value=f"{max_latency:.0f} ms" if max_latency else "—",
                help="Maximum response time in window"
            )
        with col3:
            st.metric(
                label="🎯 95th Percentile", 
                value=f"{p95_latency:.0f} ms" if p95_latency else "—",
                help="95% of requests completed within this time"
            )
        with col4:
            st.metric(
                label="📊 Std Deviation", 
                value=f"{std_latency:.1f} ms" if std_latency else "—",
                help="Measure of response time variability"
            )
    
    # Additional spacing after secondary metrics
    st.markdown('<div class="spacing-lg"></div>', unsafe_allow_html=True)

# Section Divider
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

# Enhanced Visualizations Section
if rows and PLOTLY:
    # Performance Monitoring Header
    st.markdown('<div class="section-header">📊 Performance Monitoring Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="spacing-md"></div>', unsafe_allow_html=True)
    
    # Prepare data
    x_all = [r["timestamp"] for r in rows]
    latencies = [r["latency_ms"] if r["latency_ms"] is not None else None for r in rows]
    availability = [1 if r["status"] == "up" else 0 for r in rows]
    
    # Create chart container
    with st.container():
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        
        # Create subplots with improved spacing
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=(
                "📈 Response Time Trend", "🟢 Service Availability",
                "📊 Latency Distribution", "🚨 Error Events",
                "🔥 Performance Heatmap", "💯 Health Score"
            ),
            specs=[
                [{"secondary_y": False}, {"secondary_y": False}],
                [{"secondary_y": False}, {"secondary_y": False}], 
                [{"secondary_y": False}, {"type": "indicator"}]
            ],
            vertical_spacing=0.15,  # Increased spacing
            horizontal_spacing=0.12  # Increased spacing
        )
    
    # 1. Response Time Trend with statistical bands
    valid_latencies_with_time = [(x, y) for x, y in zip(x_all, latencies) if y is not None]
    if valid_latencies_with_time:
        x_valid, y_valid = zip(*valid_latencies_with_time)
        
        # Moving average
        window_size = min(10, len(y_valid))
        if window_size > 1:
            moving_avg = pd.Series(y_valid).rolling(window=window_size, center=True).mean()
            fig.add_trace(go.Scatter(
                x=x_valid, y=moving_avg, mode="lines", name="Moving Average",
                line=dict(color="#ff6b6b", width=2), opacity=0.8
            ), row=1, col=1)
        
        # Actual values
        fig.add_trace(go.Scatter(
            x=x_valid, y=y_valid, mode="markers+lines", name="Response Time",
            line=dict(color="#4f46e5", width=1), marker=dict(size=4)
        ), row=1, col=1)
        
        # Add P95 line
        if p95_latency:
            fig.add_hline(y=p95_latency, line_dash="dash", line_color="orange", 
                         annotation_text=f"95th Percentile: {p95_latency:.0f}ms", row=1, col=1)
    
    # 2. Availability Status
    fig.add_trace(go.Scatter(
        x=x_all, y=availability, mode="lines", fill="tozeroy", name="Service Up",
        line=dict(color="#16a34a", shape="hv", width=2)
    ), row=1, col=2)
    
    # 3. Response Time Distribution (Histogram)
    if valid_latencies:
        fig.add_trace(go.Histogram(
            x=valid_latencies, nbinsx=20, name="Latency Distribution",
            marker_color="#4f46e5", opacity=0.7
        ), row=2, col=1)
    
    # 4. Error Timeline
    error_times = [r["timestamp"] for r in rows if r["status"] == "down"]
    error_types = [r.get("error", "Unknown Error") for r in rows if r["status"] == "down"]
    if error_times:
        fig.add_trace(go.Scatter(
            x=error_times, y=[1]*len(error_times), mode="markers", name="Errors",
            marker=dict(color="red", size=10, symbol="x"), text=error_types,
            hovertemplate="<b>Error:</b> %{text}<br><b>Time:</b> %{x}"
        ), row=2, col=2)
    
    # 5. Response Time Heatmap (hourly)
    if len(rows) > 24:  # Only show if we have enough data
        df = pd.DataFrame(rows)
        if 'latency_ms' in df.columns and df['latency_ms'].notna().sum() > 0:
            df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
            df['day'] = pd.to_datetime(df['timestamp']).dt.day
            heatmap_data = df.groupby(['day', 'hour'])['latency_ms'].mean().unstack(fill_value=0)
            
            if not heatmap_data.empty:
                fig.add_trace(go.Heatmap(
                    z=heatmap_data.values, x=heatmap_data.columns, y=heatmap_data.index,
                    colorscale="RdYlBu_r", name="Avg Response Time"
                ), row=3, col=1)
    
    # 6. System Health Score (Gauge)
    health_score = (uptime_pct + (100 - error_rate)) / 2 if total_requests > 0 else 0
    fig.add_trace(go.Indicator(
        mode="gauge+number+delta",
        value=health_score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Health Score"},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 50], 'color': "lightgray"},
                {'range': [50, 80], 'color': "yellow"},
                {'range': [80, 100], 'color': "green"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ), row=3, col=2)
    
    # Update layout with better spacing
    fig.update_layout(
        height=max(800, CHART_HEIGHT * 1.8),  # Ensure minimum height
        showlegend=False,
        title_text="📈 Comprehensive System Analytics",
        title_x=0.5,
        title_font_size=20,
        font=dict(size=12),
        plot_bgcolor='rgba(248,249,250,0.8)',
        paper_bgcolor='white',
        margin=dict(l=60, r=60, t=80, b=60)
    )
    
    # Update axes labels with better formatting
    fig.update_xaxes(title_text="Time", row=1, col=1, title_font_size=12)
    fig.update_yaxes(title_text="Response Time (ms)", row=1, col=1, title_font_size=12)
    fig.update_xaxes(title_text="Time", row=1, col=2, title_font_size=12)
    fig.update_yaxes(title_text="Service Status", row=1, col=2, title_font_size=12)
    fig.update_xaxes(title_text="Response Time (ms)", row=2, col=1, title_font_size=12)
    fig.update_yaxes(title_text="Frequency", row=2, col=1, title_font_size=12)
    fig.update_xaxes(title_text="Time", row=2, col=2, title_font_size=12)
    fig.update_yaxes(title_text="Error Events", row=2, col=2, title_font_size=12)
    
    # Add grid lines for better readability
    fig.update_xaxes(showgrid=True, gridcolor='rgba(0,0,0,0.1)')
    fig.update_yaxes(showgrid=True, gridcolor='rgba(0,0,0,0.1)')
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    st.markdown('</div>', unsafe_allow_html=True)  # Close chart container

elif rows:  # Fallback for when Plotly is not available
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📈 Latency Trend")
        x = [r["timestamp"] for r in rows if r["latency_ms"] is not None]
        y = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
        if x and y:
            st.line_chart({"Response Time (ms)": y}, x=x)
        else:
            st.info("No latency data available")
    
    with col2:
        st.subheader("🟢 Availability")
        x2 = [r["timestamp"] for r in rows]
        y2 = [1 if r["status"] == "up" else 0 for r in rows]
        st.area_chart({"Service Up": y2}, x=x2)
else:
    st.info("📋 No monitoring data available yet. Enable auto-probe or manually trigger a probe to start collecting metrics.")

# Section Divider with proper spacing
st.markdown('<div class="spacing-xl"></div>', unsafe_allow_html=True)
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

# Backend Activity and Incidents Section with improved layout
st.markdown('<div class="section-header">📋 Backend Operations & Incident Management</div>', unsafe_allow_html=True)
st.markdown('<div class="spacing-md"></div>', unsafe_allow_html=True)

# Use better column proportions to prevent overlap
col1, spacer, col2 = st.columns([2.5, 0.2, 1.3])

with col1:
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    st.markdown("### 📊 Database Activity Monitoring")
    
    # Try to fetch backend activity data
    activity_data = None
    try:
        r = requests.get(f"{API_BASE.rstrip('/')}/analytics/summary", timeout=5)
        if r.ok:
            activity_data = r.json()
            occupancy_data = activity_data.get("occupancy_inserts_per_minute", {})
            
            if occupancy_data:
                items = sorted(occupancy_data.items())
                x3 = [datetime.fromisoformat(k) if isinstance(k, str) else k for k, _ in items]
                y3 = [v for _, v in items]
                
                if PLOTLY:
                    # Enhanced activity chart with trend analysis
                    fig3 = go.Figure()
                    
                    # Bar chart for activity
                    fig3.add_trace(go.Bar(
                        x=x3, y=y3, name="Database Inserts", 
                        marker_color="#0ea5e9", opacity=0.8
                    ))
                    
                    # Add trend line if enough data points
                    if len(y3) > 3:
                        trend_line = np.poly1d(np.polyfit(range(len(y3)), y3, 1))
                        trend_y = [trend_line(i) for i in range(len(y3))]
                        fig3.add_trace(go.Scatter(
                            x=x3, y=trend_y, mode="lines", name="Trend",
                            line=dict(color="red", width=2, dash="dash")
                        ))
                    
                    # Enhanced layout with better styling
                    fig3.update_layout(
                        title="💾 Database Activity - Occupancy Inserts per Minute",
                        xaxis_title="Time",
                        yaxis_title="Inserts per Minute",
                        hovermode="x unified",
                        height=350,
                        plot_bgcolor='rgba(248,249,250,0.8)',
                        paper_bgcolor='white',
                        title_font_size=16,
                        margin=dict(l=50, r=50, t=50, b=50)
                    )
                    
                    # Add grid lines
                    fig3.update_xaxes(showgrid=True, gridcolor='rgba(0,0,0,0.1)')
                    fig3.update_yaxes(showgrid=True, gridcolor='rgba(0,0,0,0.1)')
                    
                    st.plotly_chart(fig3, use_container_width=True, config={'displayModeBar': False})
                    
                    # Activity statistics with better spacing
                    st.markdown('<div class="spacing-md"></div>', unsafe_allow_html=True)
                    if y3:
                        total_inserts = sum(y3)
                        avg_rate = statistics.mean(y3)
                        max_rate = max(y3)
                        
                        st.markdown("#### 📊 Activity Statistics")
                        act_col1, act_col2, act_col3 = st.columns(3, gap="small")
                        with act_col1:
                            st.metric(
                                label="📋 Total Inserts", 
                                value=f"{total_inserts:,}",
                                help="Total database inserts in timeframe"
                            )
                        with act_col2:
                            st.metric(
                                label="📈 Avg Rate/min", 
                                value=f"{avg_rate:.1f}",
                                help="Average inserts per minute"
                            )
                        with act_col3:
                            st.metric(
                                label="🚀 Peak Rate/min", 
                                value=f"{max_rate}",
                                help="Maximum inserts per minute"
                            )
                
                else:
                    st.bar_chart({"Inserts per minute": y3}, x=x3, height=350)
            else:
                st.info("📊 No recent database activity detected")
        else:
            st.warning(f"⚠️ Analytics endpoint error: HTTP {r.status_code}")
    except Exception as e:
        st.error(f"❌ Unable to fetch backend activity: {e}")
    
    # Close chart container
    st.markdown('</div>', unsafe_allow_html=True)

# Spacer column (empty)
with spacer:
    st.empty()

with col2:
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    st.markdown("### 🚨 Incident Management")
    
    # Recent incidents with better styling
    downs = [r for r in rows if r["status"] == "down"]
    if downs:
        st.markdown("#### 📊 Recent Incidents")
        
        # Show last 5 incidents with better formatting
        recent_incidents = sorted(downs, key=lambda x: x["timestamp"], reverse=True)[:5]
        
        for i, incident in enumerate(recent_incidents, 1):
            with st.expander(
                f"🚨 Incident {i} - {incident['timestamp'].strftime('%H:%M:%S')}", 
                expanded=(i==1)
            ):
                incident_time = incident['timestamp'].strftime('%Y-%m-%d %H:%M:%S %Z') if isinstance(incident['timestamp'], datetime) else str(incident['timestamp'])
                error_msg = incident.get('error') or f"HTTP {incident.get('http_status', 'Unknown')}"
                
                st.markdown(f"**🕰️ Time:** `{incident_time}`")
                st.markdown(f"**❌ Error:** `{error_msg}`")
                
                if incident.get('http_status'):
                    st.markdown(f"**📊 HTTP Status:** `{incident['http_status']}`")
                if incident.get('latency_ms'):
                    st.markdown(f"**⏱️ Response Time:** `{incident['latency_ms']:.0f}ms`")
        
        # Incident statistics with better layout
        st.markdown('<div class="spacing-md"></div>', unsafe_allow_html=True)
        st.markdown("#### 📋 Incident Statistics")
        
        incident_count_5min = len([r for r in recent_5min if r["status"] == "down"])
        incident_count_1hour = len([r for r in rows if r["timestamp"] > (datetime.now(timezone.utc) - timedelta(hours=1)) and r["status"] == "down"])
        
        # Use smaller columns for metrics in the narrow space
        inc_col1, inc_col2 = st.columns(2, gap="small")
        with inc_col1:
            st.metric(
                label="🔥 5min", 
                value=str(incident_count_5min),
                help="Incidents in last 5 minutes"
            )
        with inc_col2:
            st.metric(
                label="⏰ 1hour", 
                value=str(incident_count_1hour),
                help="Incidents in last hour"
            )
        
        if last_down_at:
            time_since_last = datetime.now(timezone.utc) - last_down_at
            st.metric(
                label="🕰️ Last Incident", 
                value=f"{int(time_since_last.total_seconds() // 60)}min ago",
                help="Time since last incident"
            )
    
    else:
        st.markdown('<div class="alert-box alert-success">✅ <strong>EXCELLENT:</strong> No incidents detected in the monitoring window</div>', unsafe_allow_html=True)
    
    # System health summary with better styling
    st.markdown('<div class="spacing-md"></div>', unsafe_allow_html=True)
    st.markdown("#### 🏅 Health Summary")
    
    # Status indicator
    if current_status == "up":
        st.markdown('<div class="alert-box alert-success" style="padding: 0.8rem; margin: 0.5rem 0;">🟢 <strong>OPERATIONAL</strong></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="alert-box alert-danger" style="padding: 0.8rem; margin: 0.5rem 0;">🔴 <strong>{current_status.upper()}</strong></div>', unsafe_allow_html=True)
    
    # Uptime indicator with color coding
    if uptime_pct >= 99.9:
        st.markdown('<div class="alert-box alert-success" style="padding: 0.8rem; margin: 0.5rem 0;">🎆 <strong>EXCELLENT</strong><br>Uptime: {:.3f}%</div>'.format(uptime_pct), unsafe_allow_html=True)
    elif uptime_pct >= 99.0:
        st.markdown('<div class="alert-box alert-warning" style="padding: 0.8rem; margin: 0.5rem 0;">🟡 <strong>GOOD</strong><br>Uptime: {:.2f}%</div>'.format(uptime_pct), unsafe_allow_html=True)
    else:
        st.markdown('<div class="alert-box alert-danger" style="padding: 0.8rem; margin: 0.5rem 0;">🟠 <strong>ATTENTION NEEDED</strong><br>Uptime: {:.2f}%</div>'.format(uptime_pct), unsafe_allow_html=True)
    
    # Close chart container
    st.markdown('</div>', unsafe_allow_html=True)

# Section Divider with proper spacing
st.markdown('<div class="spacing-xl"></div>', unsafe_allow_html=True)
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

# Raw Data Table (Optional) 
if SHOW_RAW_DATA and rows:
    st.markdown('<div class="section-header">📋 Raw Monitoring Data</div>', unsafe_allow_html=True)
    st.markdown('<div class="spacing-md"></div>', unsafe_allow_html=True)
    
    # Convert to DataFrame with better styling
    with st.container():
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        
        df = pd.DataFrame(rows)
        if not df.empty:
            # Format timestamp for display
            df['formatted_time'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
            df['status_icon'] = df['status'].map({'up': '🟢', 'down': '🔴'}).fillna('⚪')
            
            # Select and reorder columns
            display_cols = ['formatted_time', 'status_icon', 'status', 'latency_ms', 'http_status', 'error']
            display_df = df[display_cols].copy()
            display_df.columns = ['Time', 'Status', 'Status Text', 'Latency (ms)', 'HTTP Code', 'Error Message']
            
            # Style the dataframe
            styled_df = display_df.style.apply(
                lambda x: ['background-color: #f0f8f0' if x['Status Text'] == 'up' 
                          else 'background-color: #fff0f0' for _ in x], axis=1
            )
            
            st.dataframe(styled_df, use_container_width=True, height=400)
            
            # Export option with better styling
            st.markdown('<div class="spacing-md"></div>', unsafe_allow_html=True)
            csv_data = df.to_csv(index=False)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.download_button(
                    label="💾 Download Complete Dataset as CSV",
                    data=csv_data,
                    file_name=f"backend_health_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        st.markdown('</div>', unsafe_allow_html=True)

# Final Section Divider
st.markdown('<div class="spacing-xl"></div>', unsafe_allow_html=True)
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

# Enhanced Footer with better styling
st.markdown('<div class="section-header">📊 Dashboard Information</div>', unsafe_allow_html=True)
st.markdown('<div class="spacing-md"></div>', unsafe_allow_html=True)

with st.container():
    footer_col1, footer_col2, footer_col3 = st.columns(3, gap="medium")
    
    with footer_col1:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown("#### 📊 Data Sources")
        st.markdown("""
        - **Health Data:** `data/backend_health.csv`
        - **Analytics:** `/analytics/summary` endpoint  
        - **Probes:** Configurable health checks
        - **Metrics:** Real-time calculations
        """)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with footer_col2:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown("#### ⚙️ Current Configuration")
        st.markdown(f"""
        - **Monitoring Window:** {WINDOW_MIN} minutes
        - **Auto-refresh:** {REFRESH_SEC}s interval
        - **Probe Timeout:** {PROBE_TIMEOUT}s limit
        - **Chart Height:** {CHART_HEIGHT}px
        - **Raw Data Table:** {'Enabled' if SHOW_RAW_DATA else 'Disabled'}
        - **Alerts:** {'Enabled' if ENABLE_ALERTS else 'Disabled'}
        """)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with footer_col3:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown("#### 🛡️ Security & Usage")
        st.markdown("""
        ⚠️ **Security Notice:**
        - Add authentication before public deployment
        - Contains sensitive operational data
        - Monitor access logs regularly
        
        📊 **Performance:**
        - Optimized for real-time monitoring
        - Auto-scaling chart heights
        - Efficient data caching
        """)
        st.markdown('</div>', unsafe_allow_html=True)

# Final spacing and attribution
st.markdown('<div class="spacing-lg"></div>', unsafe_allow_html=True)

st.markdown("""
<div style="
    text-align: center; 
    padding: 2rem; 
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 15px;
    margin: 2rem 0;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
">
    <h4 style="margin: 0; color: white;">👨‍💻 Smart Study Map - Backend Operations Dashboard</h4>
    <p style="margin: 0.5rem 0; opacity: 0.9;">Enterprise-grade monitoring solution with real-time analytics</p>
    <small style="opacity: 0.8;">Last updated: {}</small>
</div>
""".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')), unsafe_allow_html=True)
