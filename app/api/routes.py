from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import text, inspect
from app.agent.sql_agent import generate_sql
from app.agent.validator import validate_sql
from app.database.db import get_engine
from app.agent.chart_agent import decide_chart
from app.database.uploader import upload_dataset, delete_table

router = APIRouter()

class QueryRequest(BaseModel):
    question: str
    tables: list[str]

@router.post("/query")
def query(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    tables = [t.strip() for t in request.tables if t.strip()]
    if not tables:
        raise HTTPException(status_code=400, detail="At least one table must be selected.")

    # Step 0 — Validate every requested table exists
    engine = get_engine()
    known_tables = inspect(engine).get_table_names()
    unknown = [t for t in tables if t not in known_tables]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown table(s): {', '.join(unknown)}")

    # Step 1 — Generate SQL
    try:
        sql = generate_sql(request.question.strip(), tables)
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


@router.post("/upload")
def upload(
    file: UploadFile = File(...),
    table_name: str = Form(...),
    if_exists: str = Form("fail")
):
    if not table_name.strip():
        raise HTTPException(status_code=400, detail="Table name cannot be empty.")

    try:
        result = upload_dataset(file.file, file.filename, table_name, if_exists)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")


@router.delete("/tables/{table_name}")
def remove_table(table_name: str):
    engine = get_engine()
    known_tables = inspect(engine).get_table_names()
    if table_name not in known_tables:
        raise HTTPException(status_code=400, detail=f"Unknown table: {table_name}")

    try:
        delete_table(table_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete error: {str(e)}")

    return {"deleted": table_name}


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