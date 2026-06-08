import re

BLOCKED_KEYWORDS = {"drop", "delete", "insert", "update", "alter", "truncate", "create"}

def validate_sql(sql: str) -> tuple[bool, str]:
    """
    Returns (is_valid: bool, reason: str)
    """
    if not sql or not sql.strip():
        return False, "Empty query received."

    first_word = sql.strip().split()[0].lower()

    if first_word != "select":
        return False, f"Only SELECT queries are allowed. Got: '{first_word.upper()}'"

    found_blocked = [kw for kw in BLOCKED_KEYWORDS if re.search(rf"\b{kw}\b", sql, re.IGNORECASE)]
    if found_blocked:
        return False, f"Query contains blocked keywords: {found_blocked}"

    return True, "OK"