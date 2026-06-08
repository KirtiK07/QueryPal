from sqlalchemy import inspect
from app.database.db import get_engine

def load_schema() -> str:
    engine = get_engine()
    inspector = inspect(engine)
    schema_parts = []

    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        col_defs = [f"  {col['name']} ({col['type']})" for col in columns]

        fks = inspector.get_foreign_keys(table_name)
        fk_lines = [
            f"  -- FK: {fk['constrained_columns']} → "
            f"{fk['referred_table']}({fk['referred_columns']})"
            for fk in fks
        ]

        block = f"Table: {table_name}\n" + "\n".join(col_defs + fk_lines)
        schema_parts.append(block)

    return "\n\n".join(schema_parts)