import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime

API_URL = "http://localhost:8000/query"
SCHEMA_URL = "http://localhost:8000/schema"

st.set_page_config(
    page_title="QueryPal",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@400;600;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Syne', sans-serif;
        font-size: 16px !important;
        color: #e2e8f0 !important;
    }

    .stApp { background-color: #0d0f12; color: #e2e8f0; }

    /* ── Make all default Streamlit text bigger + brighter ── */
    p, li, span, label, div {
        font-size: 15px !important;
        color: #cbd5e1 !important;
    }
    [data-testid="stMarkdownContainer"] p {
        color: #cbd5e1 !important;
        font-size: 15px !important;
    }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] div {
        color: #cbd5e1 !important;
        font-size: 14px !important;
    }

    section[data-testid="stSidebar"] {
        background-color: #111318;
        border-right: 1px solid #1e2330;
    }
    .stTextArea textarea {
        background-color: #151820 !important;
        color: #f1f5f9 !important;
        border: 1px solid #2a3040 !important;
        border-radius: 8px !important;
        font-family: 'Syne', sans-serif !important;
        font-size: 16px !important;
    }
    .stTextArea textarea:focus {
        border-color: #4f8ef7 !important;
        box-shadow: 0 0 0 2px rgba(79,142,247,0.15) !important;
    }
    .stButton > button {
        background: linear-gradient(135deg, #4f8ef7, #7c5cfc);
        color: white;
        border: none;
        border-radius: 8px;
        font-family: 'Syne', sans-serif;
        font-weight: 600;
        font-size: 15px;
        padding: 0.6rem 2rem;
        width: 100%;
        transition: opacity 0.2s;
    }
    .stButton > button:hover { opacity: 0.88; }

    .stDataFrame { border-radius: 10px; overflow: hidden; }
    div[data-testid="stDataFrame"] > div {
        background-color: #151820;
        border: 1px solid #1e2330;
        border-radius: 10px;
    }
    /* Dataframe text */
    div[data-testid="stDataFrame"] * {
        font-size: 14px !important;
        color: #e2e8f0 !important;
    }

    .metric-card {
        background: #151820;
        border: 1px solid #1e2330;
        border-radius: 10px;
        padding: 1.1rem 1.4rem;
    }
    .metric-label {
        font-size: 12px !important;
        color: #64748b !important;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 26px !important;
        font-weight: 800;
        color: #e2e8f0 !important;
    }
    .metric-value.accent { color: #4f8ef7 !important; }

    .sql-block {
        background: #0a0c10;
        border: 1px solid #1e2330;
        border-left: 3px solid #4f8ef7;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 14px !important;
        color: #93c5fd !important;
        white-space: pre-wrap;
        word-break: break-word;
    }
    .section-label {
        font-size: 12px !important;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #4f8ef7 !important;
        margin-bottom: 8px;
    }
    .history-item {
        background: #151820;
        border: 1px solid #1e2330;
        border-radius: 8px;
        padding: 0.7rem 1rem;
        margin-bottom: 8px;
        font-size: 13px !important;
        color: #94a3b8 !important;
        cursor: pointer;
        transition: border-color 0.2s;
    }
    .history-item:hover { border-color: #4f8ef7; color: #e2e8f0 !important; }

    /* ── Schema panel styles ── */
    .schema-table-name {
        font-size: 13px !important;
        font-weight: 700;
        color: #7c5cfc !important;
        margin: 10px 0 4px 0;
        letter-spacing: 0.04em;
    }
    .schema-col-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 3px 8px;
        border-radius: 4px;
        margin-bottom: 2px;
        background: #151820;
    }
    .schema-col-name {
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px !important;
        color: #93c5fd !important;
    }
    .schema-col-type {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px !important;
        color: #475569 !important;
    }
    .schema-pk {
        font-size: 10px !important;
        color: #4ade80 !important;
        background: #0f2a1a;
        border-radius: 3px;
        padding: 1px 5px;
        margin-left: 4px;
    }
    .schema-fk {
        font-size: 10px !important;
        color: #fb923c !important;
        background: #2a1500;
        border-radius: 3px;
        padding: 1px 5px;
        margin-left: 4px;
    }
    .schema-container {
        background: #0d0f12;
        border: 1px solid #1e2330;
        border-radius: 8px;
        padding: 10px 12px;
        max-height: 420px;
        overflow-y: auto;
    }

    .status-error {
        background: #2a0f0f;
        border: 1px solid #991b1b;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        color: #f87171 !important;
        font-size: 14px !important;
        font-weight: 600;
    }
    hr { border-color: #1e2330 !important; }
    h1, h2, h3 {
        font-family: 'Syne', sans-serif !important;
        color: #f1f5f9 !important;
    }
    h1 { font-size: 32px !important; }
    h2 { font-size: 22px !important; }
    h3 { font-size: 18px !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state ───────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "question_input" not in st.session_state:
    st.session_state.question_input = ""
if "schema_data" not in st.session_state:
    st.session_state.schema_data = None


# ── Fetch schema from backend ────────────────────────────────────────
def fetch_schema():
    try:
        resp = requests.get(SCHEMA_URL, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("schema", {})
    except Exception:
        pass
    return None


def render_schema_panel(schema):
    for table_info in schema:
        table_name = table_info["table"]
        columns = table_info["columns"]

        st.markdown(f"""
        <div style='color:#a78bfa;font-size:13px;font-weight:600;
        margin:10px 0 4px;cursor:pointer'>▸ {table_name}</div>
        """, unsafe_allow_html=True)

        for col in columns:
            badges = ""
            if col.get("is_pk"):
                badges += "<span style='background:#14532d;color:#4ade80;font-size:10px;padding:1px 6px;border-radius:3px;margin-left:4px'>PK</span>"
            if col.get("is_fk"):
                badges += "<span style='background:#431407;color:#fb923c;font-size:10px;padding:1px 6px;border-radius:3px;margin-left:4px'>FK</span>"

            st.markdown(f"""
            <div style='display:flex;justify-content:space-between;
            align-items:center;padding:3px 8px;border-radius:4px;
            background:#151820;margin-bottom:2px;'>
                <span style='font-size:12px;color:#cbd5e1'>{col["name"]}{badges}</span>
                <span style='font-family:JetBrains Mono,monospace;font-size:11px;
                color:#64748b'>{col["type"]}</span>
            </div>
            """, unsafe_allow_html=True)
# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔍 QueryPal")
    st.markdown(
        "<p style='color:#4f8ef7;font-size:13px;letter-spacing:0.08em'>NATURAL LANGUAGE → SQL</p>",
        unsafe_allow_html=True
    )
    st.markdown("---")

    # Query history
    st.markdown("<div class='section-label'>Query History</div>", unsafe_allow_html=True)
    if not st.session_state.history:
        st.markdown(
            "<p style='color:#475569;font-size:14px'>No queries yet.</p>",
            unsafe_allow_html=True
        )
    else:
        for i, item in enumerate(reversed(st.session_state.history[-10:])):
            label = item["question"][:40] + ("..." if len(item["question"]) > 40 else "")
            if st.button(f"↩ {label}", key=f"hist_{i}"):
                st.session_state.question_input = item["question"]
                st.session_state.last_result = item
                st.rerun()

    st.markdown("---")

    # Schema panel
    st.markdown("<div class='section-label'>Database Schema</div>", unsafe_allow_html=True)

    # Refresh button
    col_r1, col_r2 = st.columns([3, 1])
    with col_r2:
        if st.button("↻", key="refresh_schema", help="Refresh schema"):
            st.session_state.schema_data = fetch_schema()
            st.rerun()

    # Load schema once on first render
    if st.session_state.schema_data is None:
        st.session_state.schema_data = fetch_schema()

    render_schema_panel(st.session_state.schema_data)

    st.markdown("---")
    st.markdown(
        "<p style='color:#334155;font-size:12px'>Connected to PostgreSQL via SQLAlchemy</p>",
        unsafe_allow_html=True
    )


# ── Main area ────────────────────────────────────────────────────────
st.markdown("# QueryPal")
st.markdown(
    "<p style='color:#94a3b8;font-size:16px;margin-top:-12px'>Ask anything about your database in plain English.</p>",
    unsafe_allow_html=True
)
st.markdown("---")

question = st.text_area(
    label="Your question",
    placeholder="e.g. Show me the top 5 products by revenue last quarter...",
    value=st.session_state.question_input,
    height=110,
    label_visibility="collapsed"
)

col_btn, col_clear = st.columns([5, 1])
with col_btn:
    run_clicked = st.button("⚡ Run Query", use_container_width=True)
with col_clear:
    if st.button("Clear", use_container_width=True):
        st.session_state.question_input = ""
        st.session_state.last_result = None
        st.rerun()

# ── Query execution ──────────────────────────────────────────────────
if run_clicked and question.strip():
    with st.spinner("Thinking..."):
        try:
            response = requests.post(
                API_URL,
                json={"question": question.strip()},
                timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                result["question"] = question.strip()
                result["timestamp"] = datetime.now().strftime("%H:%M:%S")
                st.session_state.last_result = result
                st.session_state.history.append(result)
            else:
                error_detail = response.json().get("detail", "Unknown error")
                st.session_state.last_result = {
                    "error": error_detail,
                    "question": question
                }
        except requests.exceptions.ConnectionError:
            st.session_state.last_result = {
                "error": "Cannot connect to backend. Is FastAPI running on port 8000?",
                "question": question
            }
        except Exception as e:
            st.session_state.last_result = {"error": str(e), "question": question}
    st.rerun()

elif run_clicked and not question.strip():
    st.warning("Please type a question first.")

# ── Results ──────────────────────────────────────────────────────────
result = st.session_state.last_result

if result:
    st.markdown("---")

    if "error" in result:
        st.markdown(
            f"<div class='status-error'>⚠ {result['error']}</div>",
            unsafe_allow_html=True
        )
    else:
        # ── Metric cards ─────────────────────────────────────────────
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>Rows Returned</div>
                <div class='metric-value accent'>{result.get('row_count', 0)}</div>
            </div>""", unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>Columns</div>
                <div class='metric-value'>{len(result.get('columns', []))}</div>
            </div>""", unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>Status</div>
                <div class='metric-value' style='font-size:18px;color:#4ade80'>✓ Success</div>
            </div>""", unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>Time</div>
                <div class='metric-value' style='font-size:18px'>{result.get('timestamp', '—')}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Generated SQL ─────────────────────────────────────────────
        st.markdown("<div class='section-label'>Generated SQL</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='sql-block'>{result.get('generated_sql', '')}</div>",
            unsafe_allow_html=True
        )
        st.markdown("<br>", unsafe_allow_html=True)

        # ── Table + Chart tabs ────────────────────────────────────────
        df = pd.DataFrame(result.get("rows", []), columns=result.get("columns", []))

        if not df.empty:
            tab1, tab2 = st.tabs(["📋  Table", "📊  Chart"])

            with tab1:
                st.dataframe(df, use_container_width=True, height=400)

            with tab2:
                chart = result.get("chart", {})
                chart_type = chart.get("chart_type", "none")

                if chart.get("insight"):
                    st.markdown(f"""
                    <div style='background:#0f1e35;border:1px solid #1e3a5f;
                    border-left:3px solid #4f8ef7;border-radius:8px;
                    padding:0.8rem 1.2rem;margin-bottom:1.2rem;'>
                        <span style='font-size:12px;color:#4f8ef7;letter-spacing:0.08em;
                        text-transform:uppercase;font-weight:600'>Analyst Insight</span><br>
                        <span style='color:#e2e8f0;font-size:15px'>
                            {chart.get("insight")}
                        </span>
                    </div>
                    """, unsafe_allow_html=True)

                if chart_type == "none":
                    st.markdown(
                        "<p style='color:#475569;font-size:15px'>No chart available for this result.</p>",
                        unsafe_allow_html=True
                    )
                else:
                    x_col = chart.get("x_col")
                    y_col = chart.get("y_col")
                    title = chart.get("title", "")

                    plot_cfg = dict(
                        color_discrete_sequence=[
                            "#4f8ef7", "#7c5cfc", "#38bdf8", "#4ade80", "#fb923c"
                        ],
                        template="plotly_dark"
                    )
                    layout_cfg = dict(
                        paper_bgcolor="#0d0f12",
                        plot_bgcolor="#151820",
                        font_color="#cbd5e1",
                        font_family="Syne",
                        font_size=14,
                        title=dict(text=title, font=dict(size=18, color="#f1f5f9")),
                        margin=dict(l=20, r=20, t=50, b=20),
                        xaxis=dict(gridcolor="#1e2330", linecolor="#1e2330",
                                   tickfont=dict(size=13, color="#94a3b8")),
                        yaxis=dict(gridcolor="#1e2330", linecolor="#1e2330",
                                   tickfont=dict(size=13, color="#94a3b8")),
                    )

                    try:
                        fig = None
                        if chart_type == "bar":
                            fig = px.bar(df, x=x_col, y=y_col, **plot_cfg)
                        elif chart_type == "line":
                            fig = px.line(df, x=x_col, y=y_col, markers=True, **plot_cfg)
                        elif chart_type == "pie":
                            fig = px.pie(
                                df,
                                names=x_col,
                                values=y_col,
                                color_discrete_sequence=plot_cfg["color_discrete_sequence"]
                            )
                        elif chart_type == "scatter":
                            fig = px.scatter(df, x=x_col, y=y_col, **plot_cfg)
                        elif chart_type == "histogram":
                            fig = px.histogram(df, x=x_col, **plot_cfg)
                        else:
                            st.info("Chart type not supported.")

                        if fig:
                            fig.update_layout(**layout_cfg)
                            st.plotly_chart(fig, use_container_width=True)

                    except Exception as e:
                        st.markdown(
                            f"<p style='color:#f87171;font-size:14px'>Chart render error: {e}</p>",
                            unsafe_allow_html=True
                        )
        else:
            st.markdown(
                "<p style='color:#475569;font-size:15px'>Query returned 0 rows.</p>",
                unsafe_allow_html=True
            )