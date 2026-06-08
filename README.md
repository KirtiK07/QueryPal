# QueryPal

**Natural language to SQL — powered by LLaMA3 on Groq**

QueryPal lets you query any PostgreSQL database in plain English. Type a question, get back a table and a chart. No SQL knowledge required.

Built with FastAPI, Streamlit, LangChain, and Groq. Designed to work with any database you connect — not just a toy dataset.

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

- **Plain English queries** — type a question, get SQL + results instantly
- **Dynamic schema** — connects to your live database and reads its structure automatically. Add a table in pgAdmin and QueryPal knows about it without restarting
- **Auto visualisation** — a second AI agent looks at your results and decides the best chart type, axes, and generates an analyst insight
- **Safety validator** — only SELECT queries reach the database. DROP, DELETE, INSERT and all write operations are blocked at the gate
- **Schema panel** — live sidebar showing every table, column, type, PK and FK badges
- **Query history** — last 10 queries saved in session, one click to replay
- **Database agnostic** — swap the connection URL in `.env` to connect MySQL or SQLite instead

---

## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Backend API | FastAPI + Uvicorn | Fast, async, auto-validates requests with Pydantic |
| Frontend UI | Streamlit | Data-analyst-grade UI in pure Python |
| LLM inference | Groq (LLaMA3-70B) | 10x faster inference than equivalent OpenAI models |
| LLM orchestration | LangChain | Clean SystemMessage / HumanMessage prompt structure |
| Database ORM | SQLAlchemy | Dynamic schema inspection via inspect() API |
| Database | PostgreSQL | Industry standard relational DB |
| Charts | Plotly | Interactive charts with dark theme support |

---

## Project Structure

```
QueryPal/
├── main.py                    # FastAPI entry point
├── .env                       # Secrets — never commit this
├── requirements.txt
│
├── app/
│   ├── database/
│   │   └── db.py              # SQLAlchemy engine
│   │
│   ├── agent/
│   │   ├── schema_loader.py   # Reads live DB schema
│   │   ├── sql_agent.py       # English → SQL via LLM
│   │   ├── chart_agent.py     # Results → chart config via LLM
│   │   └── validator.py       # SELECT-only safety check
│   │
│   ├── api/
│   │   └── routes.py          # POST /query and GET /schema
│   │
│   └── ui/
│       └── streamlit_app.py   # Full frontend
│
└── tests/
    └── test_agent.py
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL running locally (pgAdmin works)
- Groq API key — free at [console.groq.com](https://console.groq.com)

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/querypal.git
cd querypal
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

Create a `.env` file in the root:

```env
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/querypal
GROQ_API_KEY=gsk_your_key_here
```

### 5. Set up your database

Create a database called `querypal` in pgAdmin (or any name — update the URL accordingly).
Run your schema SQL to create tables.

### 6. Start the backend

```bash
uvicorn main:app --reload --port 8000
```

### 7. Start the frontend

```bash
streamlit run app/ui/streamlit_app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## How It Works

```
User question (English)
        ↓
routes.py          POST /query received
        ↓
schema_loader.py   reads live DB schema via SQLAlchemy inspect()
        ↓
sql_agent.py       schema + question sent to Groq LLM → SQL returned
        ↓
validator.py       blocks anything that isn't a SELECT statement
        ↓
routes.py          SQLAlchemy executes the safe query
        ↓
chart_agent.py     result columns + rows sent to LLM → chart config returned
        ↓
Streamlit          renders table + chart + analyst insight
```

---

## API Endpoints

### `POST /query`

```json
// Request
{ "question": "Show all companies in the North region" }

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
Show all companies
How many companies are in each region?
Which region has the most companies?
List all companies alphabetically
Show companies whose name contains 'Ltd'
Which region has the least number of companies?
```

---

## Safety

QueryPal enforces read-only access at the validator layer — not just at the prompt level.

- Every generated query is checked before execution
- The first word must be `SELECT` — anything else is rejected
- Blocked keywords: `DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`, `TRUNCATE`, `CREATE`
- System tables (`pg_shadow`, `pg_authid`) are explicitly blocked in the prompt
- If the LLM cannot answer from the schema, it returns `CANNOT_GENERATE` instead of hallucinating

---

## Extending

**Connect a different database** — change one line in `.env`:
```env
# MySQL
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/dbname

# SQLite
DATABASE_URL=sqlite:///./local.db
```

**Swap the LLM** — change two lines in `sql_agent.py` and `chart_agent.py`:
```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o", temperature=0)
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | SQLAlchemy connection URL for your database |
| `GROQ_API_KEY` | API key from console.groq.com |



