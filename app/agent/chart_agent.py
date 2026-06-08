import os
import json
import re
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.3-70b-versatile",
    temperature=0,
)

CHART_SYSTEM_PROMPT = """You are a senior data analyst and visualization expert.

Your job is to look at a dataset (column names + sample rows) and decide the best way to visualize it.

## STRICT OUTPUT RULES:
- Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
- Never add text before or after the JSON.
- The JSON must match this exact structure:

{
  "chart_type": "bar" | "line" | "pie" | "scatter" | "histogram" | "none",
  "x_col": "<column name for X axis or pie labels>",
  "y_col": "<column name for Y axis or pie values — must be numeric>",
  "title": "<short chart title, max 8 words>",
  "insight": "<one sentence analyst insight about the data>"
}

## CHART SELECTION RULES:
- bar     → comparing categories (region vs count, product vs revenue)
- line    → trends over time (date/month/year on X axis)
- pie     → proportions where total adds to 100% (max 6 slices, else use bar)
- scatter → relationship between two numeric columns
- histogram → distribution of a single numeric column
- none   → data is a single value, pure text, or not visualizable

## AXIS SELECTION RULES:
- x_col must be the categorical or time column
- y_col must ALWAYS be a numeric column
- If multiple numeric columns exist, pick the most meaningful one
- Column names in your response must match EXACTLY what is in the data

## INSIGHT RULES:
- The insight must be a real observation from the data, not generic
- Example good: "North region has 2x more companies than East"
- Example bad: "The chart shows the distribution of data"
"""

def decide_chart(columns: list, rows: list) -> dict:
    """
    Takes query result columns and rows, returns chart config dict.
    Falls back to a safe default if LLM fails or returns invalid JSON.
    """
    if not rows or not columns:
        return _no_chart("Empty result set")

    # Send only first 50 rows to keep prompt small
    sample_rows = rows[:50]

    user_message = f"""## Dataset:

Columns: {columns}

Sample rows (up to 50):
{json.dumps(sample_rows, indent=2, default=str)}

Decide the best chart for this data and return the JSON."""

    try:
        response = llm.invoke([
            SystemMessage(content=CHART_SYSTEM_PROMPT),
            HumanMessage(content=user_message)
        ])

        raw = response.content.strip()

        # Strip markdown fences if LLM adds them anyway
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        chart_config = json.loads(clean)

        # Validate required keys exist
        required_keys = {"chart_type", "x_col", "y_col", "title", "insight"}
        if not required_keys.issubset(chart_config.keys()):
            return _no_chart("Incomplete chart config from LLM")

        # Validate columns actually exist in the data
        if chart_config["x_col"] not in columns:
            return _no_chart(f"x_col '{chart_config['x_col']}' not in columns")
        if chart_config["chart_type"] != "none" and chart_config["y_col"] not in columns:
            return _no_chart(f"y_col '{chart_config['y_col']}' not in columns")

        return chart_config

    except json.JSONDecodeError:
        return _no_chart("LLM returned invalid JSON")
    except Exception as e:
        return _no_chart(f"Chart agent error: {str(e)}")


def _no_chart(reason: str) -> dict:
    return {
        "chart_type": "none",
        "x_col": None,
        "y_col": None,
        "title": None,
        "insight": reason
    }