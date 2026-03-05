from __future__ import annotations

from typing import Optional

try:
    import pymssql  # type: ignore[import-untyped]
except ImportError:
    pymssql = None  # type: ignore[assignment,misc]

from src.core.config import settings
from src.core.constants import INFLOW_USER_ID_COLUMN
from src.shared.logging_config import get_logger

logger = get_logger(__name__)

_SCHEMA_CACHE: dict[str, list[str]] = {}


def _is_inflow_configured() -> bool:
    return bool(
        settings.inflow_db_host
        and settings.inflow_db_name
        and settings.inflow_db_username
        and settings.inflow_db_password
    )


def _get_connection():
    return pymssql.connect(
        server=settings.inflow_db_host,
        user=settings.inflow_db_username,
        password=settings.inflow_db_password,
        database=settings.inflow_db_name,
        port=settings.inflow_db_port,
    )


def _discover_name_columns(conn) -> list[str]:
    table = settings.inflow_user_table
    cache_key = f"{settings.inflow_db_name}.{table}"
    if cache_key in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[cache_key]

    with conn.cursor(as_dict=True) as cur:
        cur.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (table,),
        )
        rows = cur.fetchall()

    if not rows:
        _SCHEMA_CACHE[cache_key] = []
        return []

    all_columns = [r["COLUMN_NAME"] for r in rows]
    name_cols = [col for col in all_columns if "name" in col.lower()]
    _SCHEMA_CACHE[cache_key] = name_cols
    return name_cols


def lookup_user_id_by_name(person_name: str) -> Optional[int]:
    """
    Search inflow DB for a user whose name fields match the given string.
    Introspects the users table schema to find name-like columns; id column
    is always "id". Returns the first match's user ID, or None if not found.
    """
    if not person_name or not person_name.strip():
        return None
    if pymssql is None:
        logger.warning("inflow_user_lookup_skipped: pymssql_not_installed")
        return None
    if not _is_inflow_configured():
        logger.warning("inflow_user_lookup_skipped: inflow_db_not_configured")
        return None

    try:
        conn = _get_connection()
        name_cols = _discover_name_columns(conn)

        if not name_cols:
            logger.warning(
                "inflow_user_lookup_skipped: no_name_columns_in_table",
                table=settings.inflow_user_table,
            )
            conn.close()
            return None

        search_term = person_name.strip().replace("'", "''")
        conditions = " OR ".join(
            f"[{col}] LIKE N'%{search_term}%'" for col in name_cols
        )
        table = settings.inflow_user_table
        query = f"""
            SELECT TOP 1 [{INFLOW_USER_ID_COLUMN}]
            FROM [{table}]
            WHERE {conditions}
        """

        with conn.cursor(as_dict=True) as cur:
            cur.execute(query)
            row = cur.fetchone()
        conn.close()
        return row[INFLOW_USER_ID_COLUMN] if row and INFLOW_USER_ID_COLUMN in row else None
    except Exception as e:
        logger.warning(
            "inflow_user_lookup_failed: person_name=%s error=%s",
            person_name,
            str(e),
        )
        return None
