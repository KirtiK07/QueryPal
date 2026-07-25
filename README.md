# QueryPal

**Natural language to SQL — powered by LLaMA 3.3 on Groq, backed by Supabase**

QueryPal lets you upload your own data and query it in plain English. Upload a CSV or Excel file straight from the browser, ask a question, and get back the generated SQL, a results table, and an auto-generated chart with a one-line insight. No SQL knowledge required, and no separate database setup — everything runs against Supabase (managed Postgres) and deploys as a single app on Vercel.

---

## Demo

```
You:      "How many companies are in each region?"

QueryPal: SELECT region, COUNT(*) AS company_count
          FROM companies
          GROUP BY region
          ORDER BY company_count DESC
          LIMIT 100;

Result:   Table + bar chart + "North region leads with the highest concentration"
```

---

## Features

- **Upload your own data** — drop a CSV or Excel file in the browser and it becomes a real Supabase table immediately, no dashboard visit required
- **Plain English queries** — type a question, get SQL + results instantly
- **Multi-table querying** — select more than one table at once and ask questions that require a join, using each table's real foreign-key relationships as a hint
- **Dynamic schema** — reads the live database structure on every request; upload a new table or add a column in Supabase and QueryPal knows about it instantly, no restart or redeploy
- **Auto visualisation** — a second AI agent looks at your results and decides the best chart type, axes, and generates an analyst insight
- **Safety validator** — only SELECT queries reach the database. DROP, DELETE, INSERT and all write operations are blocked at the gate, independent of what the LLM was told to do
- **Self-correcting SQL generation** — if a generated query fails because of a schema mismatch (e.g. a hallucinated column name), the actual database error is fed back to the LLM for one automatic retry before surfacing anything to the user
- **Schema panel** — live sidebar showing every table, column, type, and PK/FK badges
- **Table management** — delete a table you no longer need directly from the schema panel, with a confirmation step first
- **Query history** — persisted in the browser (`localStorage`), survives a page refresh, one click to replay a past question
- **Single deployment** — frontend and backend are served from the same FastAPI app on Vercel, same origin, no CORS, no separate frontend hosting

---

## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Backend API | FastAPI + Uvicorn | Fast, async, auto-validates requests with Pydantic |
| Frontend UI | Plain HTML/CSS/JS + Bootstrap 5 | No build step, no framework — served as static files by the same backend deployment |
| LLM inference | Groq (Llama 3.3 70B) | Very fast inference for SQL generation and chart selection |
| LLM orchestration | LangChain | Structures the system/human prompt sent to the model |
| Database | Supabase (PostgreSQL) | Managed Postgres with a browser dashboard — no server to patch or back up by hand |
| Database ORM | SQLAlchemy | Dynamic schema inspection via `inspect()`, plus `to_sql()` for uploads |
| Charts | Plotly.js | Interactive charts rendered client-side, dark theme |
| Hosting | Vercel | Single deployment serves both the API and the static frontend |

---

## Project Structure

```
QueryPal/
├── main.py                    # FastAPI entry point; also mounts the static frontend
├── vercel.json                 # Vercel function config
├── .env                        # Secrets — never commit this
├── requirements.txt
│
├── app/
│   ├── database/
│   │   ├── db.py               # Two SQLAlchemy engines: pooled (queries) + direct/session (DDL)
│   │   └── uploader.py         # CSV/Excel upload (create + insert) and table delete logic
│   │
│   ├── agent/
│   │   ├── schema_loader.py   # Reads live DB schema — one table, several, or all
│   │   ├── sql_agent.py       # English → SQL via LLM, with one retry on schema-mismatch errors
│   │   ├── chart_agent.py     # Results → chart config via LLM
│   │   └── validator.py       # SELECT-only safety check
│   │
│   └── api/
│       └── routes.py          # POST /query, POST /upload, DELETE /tables/{name}, GET /schema
│
├── web/                        # Static frontend, served directly by FastAPI
│   ├── index.html
│   ├── style.css
│   └── app.js
│
└── tests/
    └── test_agent.py
```

> The original Streamlit UI (`app/ui/streamlit_app.py`) has been retired in favor of the plain HTML/JS frontend in `web/`, so that the whole app — frontend and backend — deploys as a single Vercel project instead of two separately hosted services.

---

## Getting Started

### Prerequisites

- Python 3.11+
- A [Supabase](https://supabase.com) project (free tier is enough)
- Groq API key — free at [console.groq.com](https://console.groq.com)

### 1. Clone the repo

```bash
git clone https://github.com/KirtiK07/QueryPal.git
cd QueryPal
```

### 2. Create and activate virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the root (see [Environment Variables](#environment-variables) below for where to find each value in the Supabase dashboard):

```env
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
DATABASE_URL_DIRECT=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
GROQ_API_KEY=gsk_your_key_here
MODEL_NAME=llama-3.3-70b-versatile
```

### 5. Start the app

```bash
uvicorn main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) — the frontend and API are both served from this one process. Upload a CSV or Excel file from the "Upload New Dataset" panel to get started; there's no separate schema-setup step.

---

## How It Works

```
User picks table(s) + asks a question (English)
        ↓
web/app.js         POST /query received by the browser fetch() call
        ↓
routes.py          validates the requested table(s) actually exist
        ↓
schema_loader.py   reads live schema via SQLAlchemy inspect() — scoped to
                    just the selected table(s), not the whole database
        ↓
sql_agent.py        schema + question sent to Groq LLM → SQL returned
        ↓
validator.py        blocks anything that isn't a SELECT statement
        ↓
routes.py            SQLAlchemy executes the safe query
                     (one automatic retry with the DB's own error message
                      if execution fails on a schema mismatch)
        ↓
chart_agent.py       result columns + rows sent to LLM → chart config returned
        ↓
web/app.js           renders table + Plotly.js chart + analyst insight
```

**Uploading a dataset** follows a separate, simpler path: `web/app.js` posts the file as `multipart/form-data` to `POST /upload`, which calls `app/database/uploader.py` — pandas reads the file, sanitizes every table/column name into a safe SQL identifier, and `DataFrame.to_sql()` issues the `CREATE TABLE` and row inserts together, through the Supabase **session pooler** connection (needed for reliable DDL under a serverless function — see [Environment Variables](#environment-variables)).

---

## API Endpoints

### `POST /query`

```json
// Request
{ "question": "Show all companies in the North region", "tables": ["companies"] }

// Response
{
  "question": "Show all companies in the North region",
  "generated_sql": "SELECT * FROM companies WHERE region ILIKE 'North' LIMIT 100",
  "columns": ["id", "name", "region"],
  "rows": [{ "id": 1, "name": "Tata Consultancy", "region": "North" }],
  "row_count": 2,
  "chart": {
    "chart_type": "bar",
    "x_col": "name",
    "y_col": "id",
    "title": "Companies in North Region",
    "insight": "2 companies are headquartered in the North region"
  }
}
```

`tables` accepts more than one table name for join-style questions — see [Multi-table querying](#features).

### `POST /upload`

`multipart/form-data` with fields `file`, `table_name`, and `if_exists` (`fail` | `replace` | `append`).

```json
// Response
{ "table": "companies", "row_count": 250, "columns": ["id", "name", "region"] }
```

### `DELETE /tables/{table_name}`

```json
// Response
{ "deleted": "companies" }
```

### `GET /schema`

```json
{
  "schema": [
    {
      "table": "companies",
      "columns": [
        { "name": "id",     "type": "INTEGER", "is_pk": true,  "is_fk": false },
        { "name": "name",   "type": "VARCHAR", "is_pk": false, "is_fk": false },
        { "name": "region", "type": "VARCHAR", "is_pk": false, "is_fk": false }
      ]
    }
  ]
}
```

---

## Sample Queries

```
Show all rows
How many records are in each category?
Which category has the most records?
List everything alphabetically by name
Show rows whose name contains 'Ltd'
Which group has the least number of records?
```

---

## Safety

QueryPal enforces read-only access at the validator layer — not just at the prompt level.

- Every generated query is checked before execution
- The first word must be `SELECT` — anything else is rejected
- Blocked keywords: `DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`, `TRUNCATE`, `CREATE`
- System tables (`pg_shadow`, `pg_authid`) are explicitly blocked in the prompt
- If the LLM cannot answer from the schema, it returns `CANNOT_GENERATE` instead of hallucinating
- Uploaded table and column names are sanitized into safe SQL identifiers before any `CREATE TABLE`/`INSERT` is issued — never taken as raw, unescaped input

---

## Extending

**Connect a different database** — change `DATABASE_URL` / `DATABASE_URL_DIRECT` in `.env`. The app was migrated from local PostgreSQL to Supabase without touching any SQLAlchemy code — only the connection string values changed. Any Postgres-compatible target works the same way; MySQL/SQLite are also supported by changing the URL scheme, though the two-connection (pooled + direct) split is specific to Supabase's architecture.

**Swap the LLM** — change two lines in `sql_agent.py` and `chart_agent.py`:
```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o", temperature=0)
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | Supabase **pooled** (transaction-mode, port 6543) connection string — used for all `/query` and `/schema` traffic. Find it under Project Settings → Database → Connection string → Transaction pooler. |
| `DATABASE_URL_DIRECT` | Supabase **session pooler** (port 5432, same host as `DATABASE_URL`) connection string — used only for `CREATE TABLE`/`INSERT` on upload. Must be the session pooler, not the true "Direct connection" shown in the dashboard — that one is IPv6-only and unreachable from Vercel's serverless functions. |
| `GROQ_API_KEY` | API key from console.groq.com |
| `MODEL_NAME` | Groq model used for SQL/chart generation (currently `llama-3.3-70b-versatile`) |

---

## Deployment

QueryPal deploys as a single Vercel project — no separate frontend hosting needed. Vercel's Python runtime auto-detects the FastAPI `app` instance in `main.py` at the repo root; `vercel.json` sets the function's `maxDuration`. Set the four environment variables above under the project's Production environment, then `vercel --prod`. The `web/` static files are served by the same deployment via FastAPI's `StaticFiles`, mounted after the API routes so `/query`, `/upload`, `/tables/{name}`, and `/schema` resolve first.

