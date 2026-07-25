from sqlalchemy import text
from app.database.db import get_engine


def save_query(user_id: str, question: str, generated_sql: str | None,
                tables: list[str], row_count: int | None, chart_type: str | None) -> None:
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO public.query_history (user_id, question, generated_sql, tables, row_count, chart_type)
            VALUES (:user_id, :question, :generated_sql, :tables, :row_count, :chart_type)
        """), {
            "user_id": user_id,
            "question": question,
            "generated_sql": generated_sql,
            "tables": tables,
            "row_count": row_count,
            "chart_type": chart_type,
        })
        conn.commit()


def get_history(user_id: str, limit: int = 10) -> list[dict]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT question, generated_sql, tables, row_count, chart_type, created_at
            FROM public.query_history
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT :limit
        """), {"user_id": user_id, "limit": limit}).mappings().all()
    return [dict(r) for r in rows]
