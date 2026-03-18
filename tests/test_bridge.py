"""
Mock-based tests for the legacy DB bridge without a real AS/400.

Uses a local SQLite database with "obscure" physical table names (F001, ANAG00)
and a temporary mapping config to verify that the connector, semantic mapper,
and PII masking work end-to-end.
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

# Import after setting env so test DB/mapping are used when module loads
# We will set env and clear server globals before calling query_legacy_db


@pytest.fixture
def temp_mapping_file():
    """Write a mapping.json that maps logical names to physical obscure names."""
    data = {
        "tables": {
            "Anagrafica_Clienti": "ANAG00",
            "Fatture": "F001",
        }
    }
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as f:
        json.dump(data, f, indent=2)
        path = f.name
    try:
        yield path
    finally:
        os.unlink(path)


@pytest.fixture
def sqlite_db_path(temp_mapping_file):
    """Create a SQLite DB with tables ANAG00 and F001 and sample rows."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    conn = sqlite3.connect(path)
    try:
        # Table names simulate legacy AS/400-style naming
        conn.execute("""
            CREATE TABLE ANAG00 (
                CODICE TEXT,
                RAGIONE_SOCIALE TEXT,
                CF TEXT,
                IBAN TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE F001 (
                NUMERO TEXT,
                DATA TEXT,
                CLIENTE TEXT,
                IMPORTO REAL
            )
        """)
        conn.execute(
            "INSERT INTO ANAG00 (CODICE, RAGIONE_SOCIALE, CF, IBAN) VALUES (?, ?, ?, ?)",
            ("C001", "Acme S.r.l.", "RSSMRA80A01H501U", "IT60X0542811101000000123456"),
        )
        conn.execute(
            "INSERT INTO ANAG00 (CODICE, RAGIONE_SOCIALE, CF, IBAN) VALUES (?, ?, ?, ?)",
            ("C002", "Beta S.p.A.", "GLLGNN85B02F205X", None),
        )
        conn.execute(
            "INSERT INTO F001 (NUMERO, DATA, CLIENTE, IMPORTO) VALUES (?, ?, ?, ?)",
            ("F2024-001", "2024-01-15", "C001", 1500.00),
        )
        conn.commit()
    finally:
        conn.close()
    yield path
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@pytest.fixture
def bridge_env(sqlite_db_path, temp_mapping_file):
    """Set env vars and reset server globals so the bridge uses test DB and mapping."""
    os.environ["ITALY_LEGACY_DB_URL"] = f"sqlite:///{sqlite_db_path}"
    os.environ["ITALY_LEGACY_MAPPING_PATH"] = temp_mapping_file
    # Force server to recreate connector and mapper with new env
    import app.server as server
    server._connector = None
    server._mapper = None
    yield
    # Restore defaults so other tests are not affected
    server._connector = None
    server._mapper = None
    if "ITALY_LEGACY_DB_URL" in os.environ:
        del os.environ["ITALY_LEGACY_DB_URL"]
    if "ITALY_LEGACY_MAPPING_PATH" in os.environ:
        del os.environ["ITALY_LEGACY_MAPPING_PATH"]


def test_semantic_mapper_resolves_logical_to_physical(temp_mapping_file):
    """Mapper translates Anagrafica_Clienti -> ANAG00 from config."""
    os.environ["ITALY_LEGACY_MAPPING_PATH"] = temp_mapping_file
    from app.mapper import SemanticMapper
    mapper = SemanticMapper()
    assert mapper.to_physical("Anagrafica_Clienti") == "ANAG00"
    assert mapper.to_physical("Fatture") == "F001"
    assert mapper.to_physical("Unknown_Table") == "Unknown_Table"
    del os.environ["ITALY_LEGACY_MAPPING_PATH"]


def test_connector_read_only_returns_rows(sqlite_db_path):
    """LegacyConnector executes SELECT and returns list of dicts."""
    from app.connector import LegacyConnector
    conn = LegacyConnector(f"sqlite:///{sqlite_db_path}")
    rows = conn.execute_read('SELECT * FROM ANAG00 LIMIT 10')
    conn.close()
    assert len(rows) == 2
    assert rows[0]["CODICE"] == "C001"
    assert rows[0]["RAGIONE_SOCIALE"] == "Acme S.r.l."
    assert rows[0]["CF"] == "RSSMRA80A01H501U"


def test_security_masks_cf_and_iban():
    """mask_result replaces Codice Fiscale and IBAN with placeholders."""
    from app.security import mask_result, MASK_PLACEHOLDER_CF, MASK_PLACEHOLDER_IBAN
    rows = [
        {"nome": "Mario", "cf": "RSSMRA80A01H501U", "iban": "IT60X0542811101000000123456"},
    ]
    masked = mask_result(rows)
    assert masked[0]["cf"] == MASK_PLACEHOLDER_CF
    assert masked[0]["iban"] == MASK_PLACEHOLDER_IBAN
    assert masked[0]["nome"] == "Mario"


def test_mask_sensitive_data_text_free():
    """mask_sensitive_data masks CF/IBAN occurrences in free text with [RISERVATO]."""
    from app.security import mask_sensitive_data, MASK_PLACEHOLDER_GENERIC

    text = "Cliente RSSMRA80A01H501U ha IBAN IT60X0542811101000000123456 in nota."
    out = mask_sensitive_data(text)
    assert "RSSMRA80A01H501U" not in out
    assert "IT60X0542811101000000123456" not in out
    assert MASK_PLACEHOLDER_GENERIC in out


def test_query_legacy_db_integration(bridge_env):
    """Full bridge: logical name -> physical table, query, masking."""
    from app.server import query_legacy_db
    from app.security import MASK_PLACEHOLDER_CF, MASK_PLACEHOLDER_IBAN

    # Query by logical name; should hit ANAG00
    rows = query_legacy_db("Anagrafica_Clienti", limit=10)
    assert len(rows) == 2
    assert rows[0]["CODICE"] == "C001"
    assert rows[0]["RAGIONE_SOCIALE"] == "Acme S.r.l."
    # CF and IBAN must be masked
    assert rows[0]["CF"] == MASK_PLACEHOLDER_CF
    assert rows[0]["IBAN"] == MASK_PLACEHOLDER_IBAN

    rows_fatture = query_legacy_db("Fatture", limit=10)
    assert len(rows_fatture) == 1
    assert rows_fatture[0]["NUMERO"] == "F2024-001"
    assert rows_fatture[0]["IMPORTO"] == 1500.0


def test_query_legacy_db_with_filters(bridge_env):
    """Filters are applied as equality WHERE conditions."""
    from app.server import query_legacy_db
    rows = query_legacy_db(
        "Anagrafica_Clienti",
        filters={"CODICE": "C001"},
        limit=10,
    )
    assert len(rows) == 1
    assert rows[0]["CODICE"] == "C001"

def test_query_legacy_db_with_filter_aliases(bridge_env):
    """Natural-language filter keys are normalized (e.g. cliente -> CLIENTE)."""
    from app.server import query_legacy_db
    rows = query_legacy_db(
        "Fatture",
        filters={"cliente": "C001"},
        limit=10,
    )
    assert len(rows) == 1
    assert rows[0]["CLIENTE"] == "C001"


def test_query_legacy_db_respects_limit(bridge_env):
    """limit parameter caps the number of rows."""
    from app.server import query_legacy_db
    rows = query_legacy_db("Anagrafica_Clienti", limit=1)
    assert len(rows) == 1


def test_privacy_cleanup_report():
    """privacy_cleanup returns an audit report with timestamp and status."""
    from app.privacy import run_privacy_cleanup

    report = run_privacy_cleanup()
    assert "timestamp_utc" in report
    assert "connections_closed" in report
    assert "state_reset" in report
    assert report["message"]


def test_privacy_cleanup_tool_resets_state(bridge_env):
    """Calling privacy_cleanup tool closes connector and resets server state."""
    import app.server as server

    # One query to create connector
    server.query_legacy_db("Anagrafica_Clienti", limit=1)
    assert server._connector is not None

    report = server.privacy_cleanup()
    assert report["connections_closed"] is True
    assert report["state_reset"] is True
    assert server._connector is None
    # Next query should work (recreates connector)
    rows = server.query_legacy_db("Fatture", limit=1)
    assert len(rows) == 1
