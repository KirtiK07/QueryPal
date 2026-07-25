import os
import re
import json
from datetime import datetime

import streamlit as st

# Streamlit Cloud injects credentials via st.secrets rather than a .env file.
# Mirror them into the environment before importing anything that reads
# os.getenv() at import time — app.database.db creates its engines eagerly
# on import, so this has to run first. Locally, st.secrets is just empty and
# app.database.db's own load_dotenv() picks up .env as before.
try:
    for _key, _value in st.secrets.items():
        os.environ.setdefault(_key, str(_value))
except Exception:
    pass

import pandas as pd
import plotly.express as px
from sqlalchemy import inspect, text
from sqlalchemy.exc import ProgrammingError

from app.database.db import get_engine
from app.database.uploader import upload_dataset, delete_table, suggested_table_name
from app.agent.sql_agent import generate_sql
from app.agent.validator import validate_sql
from app.agent.chart_agent import decide_chart

GITHUB_URL = "https://github.com/KirtiK07/QueryPal"

st.set_page_config(
    page_title="QueryPal — Ask Your Data Questions in Plain English",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Query orchestration (ported from the old app/api/routes.py, minus the
# HTTP framing — same validate → generate → validate → run → one retry
# → chart flow, just as plain function calls) ─────────────────────────
class QueryError(Exception):
    def __init__(self, message, generated_sql=None):
        super().__init__(message)
        self.generated_sql = generated_sql


def fetch_schema():
    try:
        engine = get_engine()
        inspector = inspect(engine)
        schema_data = []
        for table_name in inspector.get_table_names():
            columns = inspector.get_columns(table_name)
            pk_cols = inspector.get_pk_constraint(table_name).get("constrained_columns", [])
            fk_cols = {
                col
                for fk in inspector.get_foreign_keys(table_name)
                for col in fk["constrained_columns"]
            }
            col_list = [
                {
                    "name": c["name"],
                    "type": str(c["type"]),
                    "is_pk": c["name"] in pk_cols,
                    "is_fk": c["name"] in fk_cols,
                }
                for c in columns
            ]
            schema_data.append({"table": table_name, "columns": col_list})
        return schema_data
    except Exception:
        return []


def _run_sql(engine, sql):
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = list(result.keys())
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
    return columns, rows


def run_query(question, tables):
    engine = get_engine()
    known_tables = inspect(engine).get_table_names()
    unknown = [t for t in tables if t not in known_tables]
    if unknown:
        raise QueryError(f"Unknown table(s): {', '.join(unknown)}")

    try:
        sql = generate_sql(question, tables)
    except ValueError as e:
        raise QueryError(str(e))
    except Exception as e:
        raise QueryError(f"LLM error: {e}")

    is_valid, reason = validate_sql(sql)
    if not is_valid:
        raise QueryError(f"Unsafe query blocked: {reason}", generated_sql=sql)

    try:
        columns, rows = _run_sql(engine, sql)
    except ProgrammingError as e:
        try:
            retry_sql = generate_sql(question, tables, error_feedback=str(e.orig))
            is_valid, reason = validate_sql(retry_sql)
            if not is_valid:
                raise QueryError(f"Unsafe query blocked: {reason}", generated_sql=retry_sql)
            sql = retry_sql
            columns, rows = _run_sql(engine, sql)
        except QueryError:
            raise
        except Exception:
            raise QueryError(f"SQL execution error: {e}", generated_sql=sql)
    except Exception as e:
        raise QueryError(f"SQL execution error: {e}", generated_sql=sql)

    chart = decide_chart(columns, rows)
    return {
        "generated_sql": sql,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "chart": chart,
    }


# ── Friendly error messages ─────────────────────────────────────────
# Same translation rules as the old web/app.js friendlyError(), so a
# non-technical user gets plain language with the raw error tucked
# behind a "technical details" expander instead of a stack of jargon.
FRIENDLY_ERROR_RULES = [
    (re.compile(r"^CANNOT_GENERATE:", re.I),
     "I couldn't figure out how to answer that from the selected data. Try rephrasing your question, or double-check you've picked the right table(s)."),
    (re.compile(r"^Unsafe query blocked", re.I),
     "That question would have required changing your data, which isn't allowed here. Try asking a question that only looks up or summarizes information."),
    (re.compile(r"^SQL execution error", re.I),
     "Something went wrong while looking up the answer. Try rephrasing your question."),
    (re.compile(r"^LLM error", re.I),
     "The AI service didn't respond in time. Please wait a moment and try again."),
    (re.compile(r"^Unknown table", re.I),
     "One of the selected tables no longer exists. Try refreshing the schema panel."),
    (re.compile(r"^Unsupported file type", re.I),
     "That file type isn't supported — please upload a .csv, .xlsx, or .xls file."),
    (re.compile(r"^Uploaded file has no rows", re.I),
     "That file looks empty — please upload a file that has data in it."),
    (re.compile(r"^Failed to create/insert", re.I),
     "Something went wrong saving that file. Double-check the name and try again."),
]


def friendly_error(raw):
    message = str(raw or "Something went wrong.")
    for pattern, friendly in FRIENDLY_ERROR_RULES:
        if pattern.search(message):
            return friendly, message
    return message, None


def suggested_questions(selected_tables, schema_data):
    tables = [t for t in schema_data if t["table"] in selected_tables]
    if not tables:
        return []

    first = tables[0]
    suggestions = [
        f"Show all rows in {first['table']}",
        f"How many rows are in {first['table']}?",
    ]

    text_col = next(
        (c for c in first["columns"]
         if not c["is_pk"] and not c["is_fk"] and re.search(r"char|text", c["type"], re.I)),
        None
    )
    if text_col:
        suggestions.append(f"How many {first['table']} are there for each {text_col['name']}?")

    if len(tables) > 1:
        suggestions.append(f"Combine {' and '.join(t['table'] for t in tables)} and show the results")

    return suggestions[:4]


# ── Styling ──────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@400;600;800&display=swap');

    html, body, [class*="css"] { font-family: 'Syne', sans-serif; }
    .stApp { background-color: #0d0f12; }
    p, li, span, label, div { color: #cbd5e1; }

    section[data-testid="stSidebar"] { background-color: #111318; border-right: 1px solid #1e2330; }

    .stButton > button {
        background: linear-gradient(135deg, #4f8ef7, #7c5cfc);
        color: white; border: none; border-radius: 8px;
        font-family: 'Syne', sans-serif; font-weight: 600;
    }
    .stButton > button:hover { opacity: 0.88; }
    .stButton > button[kind="secondary"] {
        background: #151820; border: 1px solid #2a3040; color: #cbd5e1;
    }

    .hero-subtitle { color: #94a3b8; font-size: 16px; margin-top: -8px; max-width: 640px; }
    .trust-badges { display: flex; flex-wrap: wrap; gap: 8px; margin: 14px 0 6px; }
    .badge-trust {
        font-size: 12px; padding: 5px 10px; border-radius: 999px;
        background-color: #151820; border: 1px solid #1e2330; color: #94a3b8;
    }

    .stepper { display: flex; gap: 8px; margin: 18px 0 22px; }
    .step {
        flex: 1; padding: 10px 14px; border-radius: 10px;
        background-color: #151820; border: 1px solid #1e2330;
        color: #64748b; font-size: 13px; font-weight: 600;
    }
    .step .num {
        display: inline-flex; width: 20px; height: 20px; border-radius: 50%;
        align-items: center; justify-content: center; margin-right: 8px;
        background: #0d0f12; border: 1px solid #1e2330; font-size: 11px;
    }
    .step.active { border-color: #4f8ef7; color: #e2e8f0; }
    .step.active .num { border-color: #4f8ef7; color: #4f8ef7; }
    .step.done { border-color: #4ade80; color: #e2e8f0; }
    .step.done .num { background: #4ade80; border-color: #4ade80; color: #08130b; }

    .metric-card { background: #151820; border: 1px solid #1e2330; border-radius: 10px; padding: 1.1rem 1.4rem; }
    .metric-label { font-size: 12px; color: #64748b; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 4px; }
    .metric-value { font-size: 26px; font-weight: 800; color: #e2e8f0; }
    .metric-value.accent { color: #4f8ef7; }

    .insight-banner {
        padding: 16px 18px; border-radius: 10px; margin-bottom: 18px;
        background: linear-gradient(135deg, rgba(79,142,247,0.15), rgba(124,92,252,0.15));
        border: 1px solid rgba(79,142,247,0.35);
    }
    .insight-banner .label { font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; font-weight: 700; color: #4f8ef7; display: block; }
    .insight-banner .text { font-size: 17px; font-weight: 600; color: #e2e8f0; }

    .sql-block {
        background: #0a0c10; border: 1px solid #1e2330; border-left: 3px solid #4f8ef7;
        border-radius: 8px; padding: 1rem 1.2rem; font-family: 'JetBrains Mono', monospace;
        font-size: 13px; color: #93c5fd; white-space: pre-wrap; word-break: break-word;
    }
    .section-label { font-size: 12px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #4f8ef7; margin-bottom: 8px; }

    .schema-table-name { font-size: 13px; font-weight: 700; color: #a78bfa; margin: 10px 0 4px 0; }
    .schema-col-row { display: flex; justify-content: space-between; align-items: center; padding: 3px 8px; border-radius: 4px; margin-bottom: 2px; background: #151820; }
    .schema-col-name { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #93c5fd; }
    .schema-col-type { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #475569; }
    .badge-pk { font-size: 10px; color: #4ade80; background: #0f2a1a; border-radius: 3px; padding: 1px 5px; margin-left: 4px; }
    .badge-fk { font-size: 10px; color: #fb923c; background: #2a1500; border-radius: 3px; padding: 1px 5px; margin-left: 4px; }

    .status-error { background: #2a0f0f; border: 1px solid #991b1b; border-radius: 8px; padding: 0.6rem 1rem; color: #f87171; font-weight: 600; }
    .app-footer { text-align: center; color: #475569; font-size: 12.5px; padding: 24px 0 8px; }
    .app-footer a { color: #64748b; }
    hr { border-color: #1e2330 !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state ────────────────────────────────────────────────────
st.session_state.setdefault("history", [])
st.session_state.setdefault("last_result", None)
st.session_state.setdefault("question_input", "")
st.session_state.setdefault("schema_data", None)

if st.session_state.schema_data is None:
    st.session_state.schema_data = fetch_schema()


# ── Delete confirmation (replaces the old browser confirm()) ──────────
@st.dialog("Delete this dataset?")
def confirm_delete_dialog(table_name):
    st.write(f"This will permanently remove **{table_name}** and all of its data. This can't be undone.")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", use_container_width=True):
        st.rerun()
    if c2.button("Delete permanently", use_container_width=True, type="primary"):
        try:
            delete_table(table_name)
            st.session_state.schema_data = fetch_schema()
            st.success(f"'{table_name}' deleted.")
        except Exception as e:
            st.error(friendly_error(str(e))[0])
        st.rerun()


@st.dialog("How QueryPal works")
def how_it_works_dialog():
    st.markdown("""
1. **Upload** a CSV or Excel file — it becomes a real table instantly, no setup needed.
2. **Pick** the table (or tables) your question is about.
3. **Ask** your question in plain English. An AI model turns it into SQL behind the scenes.
4. Every query is checked and only allowed to **read** data — nothing is ever changed or deleted.
5. You get back a **table**, an auto-picked **chart**, and a one-line **insight** summarizing the answer.
    """)


# ── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔍 QueryPal")
    st.markdown("<p style='color:#4f8ef7;font-size:13px;letter-spacing:0.08em'>NATURAL LANGUAGE → SQL</p>", unsafe_allow_html=True)
    st.markdown("---")

    st.markdown("<div class='section-label'>Query History</div>", unsafe_allow_html=True)
    if not st.session_state.history:
        st.markdown("<p style='color:#475569;font-size:14px'>No queries yet.</p>", unsafe_allow_html=True)
    else:
        for i, item in enumerate(reversed(st.session_state.history[-10:])):
            label = item["question"][:40] + ("…" if len(item["question"]) > 40 else "")
            if st.button(f"↩ {label}", key=f"hist_{i}", use_container_width=True, type="secondary"):
                st.session_state.question_input = item["question"]
                for t in item.get("tables", []):
                    st.session_state[f"tbl_{t}"] = True
                st.session_state.last_result = item
                st.rerun()

    st.markdown("---")

    col_lbl, col_refresh = st.columns([3, 1])
    col_lbl.markdown("<div class='section-label'>Your Tables</div>", unsafe_allow_html=True)
    if col_refresh.button("↻", key="refresh_schema", help="Refresh"):
        st.session_state.schema_data = fetch_schema()
        st.rerun()
    st.caption("Think of each table like a tab in a spreadsheet.")

    if not st.session_state.schema_data:
        st.markdown("<p style='color:#475569;font-size:14px'>No tables found. Upload a dataset to get started.</p>", unsafe_allow_html=True)
    else:
        for t in st.session_state.schema_data:
            col_name, col_del = st.columns([4, 1])
            col_name.markdown(f"<div class='schema-table-name'>▸ {t['table']}</div>", unsafe_allow_html=True)
            if col_del.button("🗑", key=f"del_{t['table']}", help="Delete this dataset"):
                confirm_delete_dialog(t["table"])
            for c in t["columns"]:
                badges = ""
                if c["is_pk"]:
                    badges += "<span class='badge-pk' title='Uniquely identifies each row'>Unique ID</span>"
                if c["is_fk"]:
                    badges += "<span class='badge-fk' title='Connects to another table'>Linked</span>"
                st.markdown(f"""
                <div class='schema-col-row'>
                    <span class='schema-col-name'>{c['name']}{badges}</span>
                    <span class='schema-col-type'>{c['type']}</span>
                </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("<p style='color:#334155;font-size:12px'>🔒 Read-only — QueryPal can look up and summarize your data, but it can never change or delete it through a question.</p>", unsafe_allow_html=True)


# ── Top bar ──────────────────────────────────────────────────────────
col_title, col_how, col_gh = st.columns([6, 1.4, 1.4])
col_title.markdown("# QueryPal")
if col_how.button("ℹ️ How it works", use_container_width=True, type="secondary"):
    how_it_works_dialog()
col_gh.link_button("GitHub ↗", GITHUB_URL, use_container_width=True)

st.markdown("<p class='hero-subtitle'>Upload a spreadsheet, type a question in plain English, and get a table, a chart, and a one-line answer back. No SQL required.</p>", unsafe_allow_html=True)
st.markdown("""
<div class='trust-badges'>
    <span class='badge-trust'>🔒 Your data is never modified</span>
    <span class='badge-trust'>⚡ Powered by Llama 3.3 on Groq</span>
    <span class='badge-trust'>🗄 Backed by Supabase (Postgres)</span>
</div>
""", unsafe_allow_html=True)

# ── Stepper ──────────────────────────────────────────────────────────
_has_data = bool(st.session_state.schema_data)
_selected_now = [
    t["table"] for t in (st.session_state.schema_data or [])
    if st.session_state.get(f"tbl_{t['table']}")
]
_has_selection = bool(_selected_now)
_has_question = bool(st.session_state.question_input.strip())

def _step_class(done, active):
    if done:
        return "step done"
    if active:
        return "step active"
    return "step"

st.markdown(f"""
<div class='stepper'>
    <div class='{_step_class(_has_data, True)}'><span class='num'>{"✓" if _has_data else "1"}</span>Upload your data</div>
    <div class='{_step_class(_has_selection, _has_data and not _has_selection)}'><span class='num'>{"✓" if _has_selection else "2"}</span>Choose what to ask about</div>
    <div class='{_step_class(_has_question, _has_selection and not _has_question)}'><span class='num'>{"✓" if _has_question else "3"}</span>Ask a question</div>
</div>
""", unsafe_allow_html=True)

# ── Step 1: Upload ──────────────────────────────────────────────────
with st.expander("📤 Step 1 — Upload a dataset (CSV or Excel)", expanded=not _has_data):
    uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=["csv", "xlsx", "xls"], label_visibility="collapsed")
    if uploaded_file is not None:
        new_table_name = st.text_input("Name this dataset", value=suggested_table_name(uploaded_file.name))
        with st.expander("Advanced options"):
            mode_label = st.selectbox(
                "If a dataset with this name already exists:",
                ["Don't upload — keep the existing one", "Replace it entirely", "Add these rows to it"]
            )
        mode_map = {
            "Don't upload — keep the existing one": "fail",
            "Replace it entirely": "replace",
            "Add these rows to it": "append",
        }
        if st.button("Upload"):
            try:
                with st.spinner("Creating table and loading data…"):
                    result = upload_dataset(uploaded_file, uploaded_file.name, new_table_name, mode_map[mode_label])
                st.success(f"Loaded {result['row_count']} rows into '{result['table']}' ({len(result['columns'])} columns). You're ready for Step 2 below.")
                st.session_state.schema_data = fetch_schema()
                st.session_state[f"tbl_{result['table']}"] = True
                st.rerun()
            except Exception as e:
                st.error(friendly_error(str(e))[0])

# ── Step 2: Choose tables ───────────────────────────────────────────
st.markdown("<div class='section-label'>Step 2 — What do you want to ask about?</div>", unsafe_allow_html=True)
if not st.session_state.schema_data:
    st.caption("Upload a dataset above to get started.")
else:
    cols = st.columns(min(4, len(st.session_state.schema_data)) or 1)
    for i, t in enumerate(st.session_state.schema_data):
        with cols[i % len(cols)]:
            with st.container(border=True):
                st.checkbox(f"**{t['table']}**", key=f"tbl_{t['table']}")
                st.caption(f"{len(t['columns'])} column{'s' if len(t['columns']) != 1 else ''}")
    st.caption("Pick one table, or a few related ones if your question needs to combine them.")

selected_tables = [
    t["table"] for t in (st.session_state.schema_data or [])
    if st.session_state.get(f"tbl_{t['table']}")
]

# ── Step 3: Ask ─────────────────────────────────────────────────────
st.markdown("<div class='section-label'>Step 3 — Ask your question</div>", unsafe_allow_html=True)
question = st.text_area(
    "Your question", placeholder="e.g. Show me the top 5 products by revenue last quarter...",
    key="question_input", height=110, label_visibility="collapsed"
)

if selected_tables:
    chips = suggested_questions(selected_tables, st.session_state.schema_data)
    if chips:
        chip_cols = st.columns(len(chips))
        for i, chip in enumerate(chips):
            if chip_cols[i].button(chip, key=f"chip_{i}", type="secondary", use_container_width=True):
                st.session_state.question_input = chip
                st.rerun()

col_run, col_clear = st.columns([5, 1])
run_clicked = col_run.button("⚡ Get My Answer", use_container_width=True)
if col_clear.button("Clear", use_container_width=True, type="secondary"):
    st.session_state.question_input = ""
    for t in (st.session_state.schema_data or []):
        st.session_state[f"tbl_{t['table']}"] = False
    st.session_state.last_result = None
    st.rerun()

# ── Query execution ──────────────────────────────────────────────────
if run_clicked:
    if not question.strip() or not selected_tables:
        st.warning("Please pick at least one table and type a question first.")
    else:
        with st.spinner("🤔 Thinking…"):
            try:
                result = run_query(question.strip(), selected_tables)
                result["question"] = question.strip()
                result["tables"] = selected_tables
                result["timestamp"] = datetime.now().strftime("%H:%M:%S")
                st.session_state.last_result = result
                st.session_state.history.append(result)
            except QueryError as e:
                friendly, raw = friendly_error(str(e))
                st.session_state.last_result = {
                    "error": friendly, "raw_error": raw, "generated_sql": e.generated_sql,
                    "question": question, "tables": selected_tables,
                }
            except Exception as e:
                friendly, raw = friendly_error(str(e))
                st.session_state.last_result = {"error": friendly, "raw_error": raw, "question": question, "tables": selected_tables}
        st.rerun()

# ── Results ──────────────────────────────────────────────────────────
result = st.session_state.last_result

if result:
    st.markdown("---")

    if "error" in result:
        st.markdown(f"<div class='status-error'>⚠ {result['error']}</div>", unsafe_allow_html=True)
        if result.get("raw_error") or result.get("generated_sql"):
            with st.expander("Show technical details"):
                if result.get("raw_error"):
                    st.markdown(f"<div class='sql-block'>{result['raw_error']}</div>", unsafe_allow_html=True)
                if result.get("generated_sql"):
                    st.markdown(f"<div class='sql-block'>{result['generated_sql']}</div>", unsafe_allow_html=True)
    else:
        chart = result.get("chart", {})
        if chart.get("insight"):
            st.markdown(f"""
            <div class='insight-banner'>
                <span class='label'>Your Answer</span>
                <span class='text'>{chart['insight']}</span>
            </div>""", unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        for col, label, value, extra_class in [
            (c1, "Rows Returned", result.get("row_count", 0), "accent"),
            (c2, "Columns", len(result.get("columns", [])), ""),
            (c3, "Status", "✓ Success", ""),
            (c4, "Time", result.get("timestamp", "—"), ""),
        ]:
            col.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>{label}</div>
                <div class='metric-value {extra_class}'>{value}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        df = pd.DataFrame(result.get("rows", []), columns=result.get("columns", []))

        if not df.empty:
            tab1, tab2 = st.tabs(["📋  Table", "📊  Chart"])
            with tab1:
                st.dataframe(df, use_container_width=True, height=400)
            with tab2:
                chart_type = chart.get("chart_type", "none")
                if chart_type == "none":
                    st.caption("No chart available for this result.")
                else:
                    x_col, y_col, title = chart.get("x_col"), chart.get("y_col"), chart.get("title", "")
                    plot_cfg = dict(color_discrete_sequence=["#4f8ef7", "#7c5cfc", "#38bdf8", "#4ade80", "#fb923c"], template="plotly_dark")
                    layout_cfg = dict(
                        paper_bgcolor="#0d0f12", plot_bgcolor="#151820", font_color="#cbd5e1",
                        font_family="Syne", title=dict(text=title, font=dict(size=18, color="#f1f5f9")),
                        margin=dict(l=20, r=20, t=50, b=20),
                        xaxis=dict(gridcolor="#1e2330", linecolor="#1e2330"),
                        yaxis=dict(gridcolor="#1e2330", linecolor="#1e2330"),
                    )
                    try:
                        fig = None
                        if chart_type == "bar":
                            fig = px.bar(df, x=x_col, y=y_col, **plot_cfg)
                        elif chart_type == "line":
                            fig = px.line(df, x=x_col, y=y_col, markers=True, **plot_cfg)
                        elif chart_type == "pie":
                            fig = px.pie(df, names=x_col, values=y_col, color_discrete_sequence=plot_cfg["color_discrete_sequence"])
                        elif chart_type == "scatter":
                            fig = px.scatter(df, x=x_col, y=y_col, **plot_cfg)
                        elif chart_type == "histogram":
                            fig = px.histogram(df, x=x_col, **plot_cfg)
                        if fig:
                            fig.update_layout(**layout_cfg)
                            st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.caption(f"Chart render error: {e}")
        else:
            st.caption("No matching rows found.")

        with st.expander("🔧 View technical details (generated SQL query)"):
            st.markdown(f"<div class='sql-block'>{result.get('generated_sql', '')}</div>", unsafe_allow_html=True)

st.markdown(f"""
<div class='app-footer'>
    Built with Streamlit, LangChain, Groq (Llama 3.3) &amp; Supabase ·
    <a href='{GITHUB_URL}' target='_blank'>View source on GitHub ↗</a>
</div>
""", unsafe_allow_html=True)
