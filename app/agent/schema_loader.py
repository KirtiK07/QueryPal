from sqlalchemy import inspect
from app.database.db import get_engine

def load_schema(table_name: str | None = None) -> str:
    engine = get_engine()
    inspector = inspect(engine)
    schema_parts = []

    table_names = [table_name] if table_name else inspector.get_table_names()

    for name in table_names:
        columns = inspector.get_columns(name)
        col_defs = [f"  {col['name']} ({col['type']})" for col in columns]

        fks = inspector.get_foreign_keys(name)
        fk_lines = [
            f"  -- FK: {fk['constrained_columns']} → "
            f"{fk['referred_table']}({fk['referred_columns']})"
            for fk in fks
        ]

        block = f"Table: {name}\n" + "\n".join(col_defs + fk_lines)
        schema_parts.append(block)

    return "\n\n".join(schema_parts)