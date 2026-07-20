from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text, inspect
from app.agent.sql_agent import generate_sql
from app.agent.validator import validate_sql
from app.database.db import get_engine
from app.agent.chart_agent import decide_chart

router = APIRouter()

class QueryRequest(BaseModel):
    question: str
    table: str

@router.post("/query")
def query(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    if not request.table.strip():
        raise HTTPException(status_code=400, detail="Table cannot be empty.")

    # Step 0 — Validate table exists
    engine = get_engine()
    known_tables = inspect(engine).get_table_names()
    if request.table not in known_tables:
        raise HTTPException(status_code=400, detail=f"Unknown table: {request.table}")

    # Step 1 — Generate SQL
    try:
        sql = generate_sql(request.question.strip(), request.table)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

    # Step 2 — Validate
    is_valid, reason = validate_sql(sql)
    if not is_valid:
        raise HTTPException(status_code=400, detail={
            "error": f"Unsafe query blocked: {reason}",
            "generated_sql": sql
        })

    # Step 3 — Execute
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": f"SQL execution error: {str(e)}",
            "generated_sql": sql
        })

    # Step 4 — Decide chart
    chart_config = decide_chart(columns, rows)

    return {
        "question": request.question,
        "generated_sql": sql,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "chart": chart_config
    }


@router.get("/schema")
def get_schema():
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

            col_list = []
            for col in columns:
                col_list.append({
                    "name": col["name"],
                    "type": str(col["type"]),
                    "is_pk": col["name"] in pk_cols,
                    "is_fk": col["name"] in fk_cols,
                })

            schema_data.append({
                "table": table_name,
                "columns": col_list
            })

        return {"schema": schema_data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schema fetch error: {str(e)}")