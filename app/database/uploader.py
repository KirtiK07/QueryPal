import re
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError
from app.database.db import get_direct_engine


def _sanitize_identifier(name: str, fallback: str) -> str:
    name = str(name).strip().lower()
    name = re.sub(r"[^a-z0-9_]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name:
        name = fallback
    if name[0].isdigit():
        name = f"t_{name}"
    return name[:63]


def _dedupe(names: list) -> list:
    seen = {}
    result = []
    for name in names:
        if name not in seen:
            seen[name] = 0
            result.append(name)
        else:
            seen[name] += 1
            result.append(f"{name}_{seen[name]}")
    return result


def suggested_table_name(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0]
    return _sanitize_identifier(stem, fallback="uploaded_table")


def read_dataset(file, filename: str) -> pd.DataFrame:
    """Reads an uploaded CSV/Excel file into a DataFrame with sanitized column names."""
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "csv":
        df = pd.read_csv(file)
    elif ext in ("xlsx", "xls"):
        df = pd.read_excel(file)
    else:
        raise ValueError(f"Unsupported file type: .{ext} (use .csv, .xlsx, or .xls)")

    df.columns = _dedupe([_sanitize_identifier(c, fallback="column") for c in df.columns])
    return df


def upload_dataset(file, filename: str, table_name: str, if_exists: str = "fail") -> dict:
    """
    Reads the uploaded file and writes it to Supabase via the direct connection,
    issuing CREATE TABLE (if needed) + INSERT through SQLAlchemy's to_sql().
    if_exists: "fail" | "replace" | "append" (same semantics as pandas.DataFrame.to_sql)
    """
    if if_exists not in ("fail", "replace", "append"):
        raise ValueError(f"Invalid if_exists mode: {if_exists}")

    table_name = _sanitize_identifier(table_name, fallback="uploaded_table")
    df = read_dataset(file, filename)

    if df.empty:
        raise ValueError("Uploaded file has no rows.")

    engine = get_direct_engine()
    try:
        df.to_sql(table_name, engine, if_exists=if_exists, index=False)
    except SQLAlchemyError as e:
        raise ValueError(f"Failed to create/insert into '{table_name}': {e}")

    return {
        "table": table_name,
        "row_count": len(df),
        "columns": list(df.columns),
    }
