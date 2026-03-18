"""
MCP Server: exposes query_legacy_db tool over stdio.

The AI can query legacy tables using logical names (e.g. Anagrafica_Clienti);
results are masked for Codice Fiscale and IBAN before being returned.
"""

import os
import re
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from app.connector import LegacyConnector
from app.mapper import SemanticMapper
from app.privacy import is_auto_cleanup_enabled, run_privacy_cleanup
from app.security import mask_result

def _get_database_url() -> str:
    """Read connection string from env at runtime (so tests can override)."""
    return os.environ.get("ITALY_LEGACY_DB_URL", "sqlite:///:memory:")

# Lazy singletons for connector and mapper
_connector: Optional[LegacyConnector] = None
_mapper: Optional[SemanticMapper] = None


def _get_connector() -> LegacyConnector:
    global _connector
    if _connector is None:
        _connector = LegacyConnector(_get_database_url())
    return _connector


def _get_mapper() -> SemanticMapper:
    global _mapper
    if _mapper is None:
        _mapper = SemanticMapper()
    return _mapper


def _reset_state() -> None:
    """Azzera connector e mapper (per pulizia privacy). La prossima richiesta li ricrea."""
    global _connector, _mapper
    _connector = None
    _mapper = None


def _safe_identifier(name: str) -> bool:
    """Allow only alphanumeric and underscore for table/column names (no SQL injection)."""
    return bool(name) and re.match(r"^[A-Za-z0-9_]+$", name) is not None


_FILTER_COLUMN_ALIASES: dict[str, str] = {
    # Common Italian / business synonyms -> typical legacy uppercase columns
    "cliente": "CLIENTE",
    "codice_cliente": "CLIENTE",
    "id_cliente": "CLIENTE",
    "customer": "CLIENTE",
    "codice": "CODICE",
    "ragione_sociale": "RAGIONE_SOCIALE",
    "partita_iva": "PIVA",
    "piva": "PIVA",
    "iban": "IBAN",
    "cf": "CF",
    "codice_fiscale": "CF",
}


def _normalize_filter_column(name: str) -> str:
    """
    Normalize filter column names to increase robustness.

    Claude prompts often use natural-language keys (e.g. \"cliente\") while the
    legacy schema uses uppercase identifiers (e.g. \"CLIENTE\"). We:
    - trim whitespace
    - replace spaces with underscores
    - apply a small alias map
    - default to uppercasing
    """
    key = (name or "").strip().replace(" ", "_")
    if not key:
        return key
    alias = _FILTER_COLUMN_ALIASES.get(key.lower())
    return alias or key.upper()


def _query_legacy_db_impl(
    table_name: str,
    filters: Optional[dict[str, Any]] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Query a legacy database table using a logical table name.

    The table_name is translated to the physical name via the semantic mapping
    (e.g. Anagrafica_Clienti -> ANAG00F). Results are read-only and sensitive
    fields (Codice Fiscale, IBAN) are masked.

    :param table_name: Logical table name (e.g. 'Anagrafica_Clienti').
    :param filters: Optional dict of column -> value for equality filters.
    :param limit: Maximum number of rows to return (default 100, max 1000).
    :return: List of row dicts with PII masked.
    """
    mapper = _get_mapper()
    physical = mapper.to_physical(table_name)
    if not _safe_identifier(physical):
        return []

    limit = max(0, min(1000, limit))
    filters = filters or {}
    params: dict[str, Any] = {"limit": limit}
    conditions: list[str] = []

    for col, val in filters.items():
        col_norm = _normalize_filter_column(str(col))
        if not _safe_identifier(col_norm):
            continue
        key = f"p_{col_norm}"
        params[key] = val
        conditions.append(f'"{col_norm}" = :{key}')

    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f'SELECT * FROM "{physical}"{where_clause} LIMIT :limit'
    connector = _get_connector()
    try:
        rows = connector.execute_read(sql, params)
        return mask_result(rows)
    finally:
        # Pulizia automatica privacy: chiudi connessioni e azzera stato dopo ogni query
        if is_auto_cleanup_enabled():
            run_privacy_cleanup(
                connector=connector,
                reset_state_callback=_reset_state,
            )


# FastMCP server with stdio as default transport
mcp = FastMCP(
    "Italy Legacy DB AI Bridge",
    json_response=True,
)


@mcp.tool()
def query_legacy_db(
    table_name: str,
    filters: Optional[dict[str, Any]] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Query a legacy database table by logical name.

    Use the logical table name (e.g. Anagrafica_Clienti); it is translated to the
    physical table (e.g. ANAG00F). Optional filters: dict of column name to value
    for equality. limit caps the number of rows (default 100, max 1000).
    Results are read-only and Codice Fiscale / IBAN are masked.
    """
    return _query_legacy_db_impl(
        table_name=table_name, filters=filters, limit=limit
    )


@mcp.tool()
def privacy_cleanup() -> dict[str, Any]:
    """
    Esegue la pulizia per la privacy: chiude tutte le connessioni al DB e azzera
    lo stato interno del server. Nessun dato sensibile resta in memoria.
    Restituisce un report di audit (timestamp, connessioni chiuse, stato azzerato).
    Utile per conformità GDPR e per dare garanzie alle aziende sulla retention dei dati.
    """
    connector = _connector
    report = run_privacy_cleanup(
        connector=connector,
        reset_state_callback=_reset_state,
    )
    return report


def main() -> None:
    """Run the MCP server over stdio (for Claude Desktop and other MCP clients)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
