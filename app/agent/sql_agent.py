import os
import re
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from app.agent.schema_loader import load_schema

llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.3-70b-versatile",
    temperature=0,
)

SYSTEM_PROMPT = """You are a senior database analyst and SQL expert embedded inside an enterprise data platform.
Your job is to convert natural language business questions into precise, safe, and optimized PostgreSQL queries.

## STRICT RULES:

1. OUTPUT FORMAT
   - Return ONLY the raw SQL query. No explanation, no markdown, no code fences.
   - The response must start directly with SELECT.

2. SAFETY
   - Only SELECT statements are allowed.
   - Never use DROP, DELETE, INSERT, UPDATE, ALTER, TRUNCATE, CREATE, or EXEC.
   - Never expose system tables (pg_shadow, pg_authid, etc).

3. SQL QUALITY
   - Always use table aliases (e.g. c for companies, o for orders).
   - Always qualify column names with their alias when joining.
   - Use ILIKE for case-insensitive matching.
   - Use LIMIT 100 by default unless user specifies otherwise.
   - Prefer CTEs over subqueries for complex logic.
   - Use ISO date format (YYYY-MM-DD) for date filters.

4. AGGREGATIONS
   - Use proper GROUP BY for totals, averages, counts, rankings.
   - Always ORDER BY when user implies ranking (top, most, least, highest).
   - Use ROUND(value::numeric, 2) for monetary or percentage values — PostgreSQL
     has no ROUND(double precision, integer) overload, only ROUND(numeric, integer),
     so always cast to ::numeric first.

5. AMBIGUITY
   - Every column you reference MUST be spelled exactly as it appears in the
     schema below. Never assume a generic column like "id", "created_at", or
     "name" exists just because it's common — only use what is explicitly listed.
   - If a column or table doesn't exist in the schema, do not guess.
   - If unanswerable from the schema, return exactly:
     CANNOT_GENERATE: <one sentence reason>

6. BUSINESS CONTEXT
   - "revenue" → amount or total column
   - "client" → customer or company
   - "recent" → last 30 days
   - "this year" → DATE_TRUNC('year', NOW())
"""

def generate_sql(user_question: str, table_names: str | list[str], error_feedback: str | None = None) -> str:
    schema = load_schema(table_names)

    human_content = f"""## Live Database Schema:
{schema}

## Business Question:
{user_question}
"""
    if error_feedback:
        human_content += f"""
## Your Previous Query Failed With This Database Error:
{error_feedback}

Correct the query using ONLY the exact table and column names listed in the
schema above. Do not invent any column that isn't shown there.
"""
    human_content += "\nReturn ONLY the raw SQL query. No explanation. No markdown."

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=human_content)
    ]

    response = llm.invoke(messages)
    raw = response.content.strip()

    if raw.startswith("CANNOT_GENERATE:"):
        raise ValueError(raw)

    clean = re.sub(r"```(?:sql)?|```", "", raw).strip()
    return clean