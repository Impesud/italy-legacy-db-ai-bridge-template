#!/usr/bin/env python3
"""
Crea il database SQLite di demo con tabelle dai nomi fisici legacy (ANAG00F, F001, ...).

Esegui dalla root del progetto:
  python scripts/create_demo_db.py

Il file viene creato in data/legacy.db. Poi imposta:
  export ITALY_LEGACY_DB_URL="sqlite:///$(pwd)/data/legacy.db"
"""

import sqlite3
import sys
from pathlib import Path

# Path della root del progetto (parent di scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "legacy.db"


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if DB_PATH.exists():
        print(f"Database già presente: {DB_PATH}")
        try:
            reply = input("Sovrascrivere? [y/N]: ").strip().lower()
            if reply != "y":
                print("Operazione annullata.")
                sys.exit(0)
        except EOFError:
            sys.exit(0)

    conn = sqlite3.connect(DB_PATH)

    # Tabelle con nomi fisici come in config/mapping.json
    conn.execute("""
        CREATE TABLE ANAG00F (
            CODICE TEXT,
            RAGIONE_SOCIALE TEXT,
            CF TEXT,
            IBAN TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE FORN00F (
            CODICE TEXT,
            RAGIONE_SOCIALE TEXT,
            PIVA TEXT,
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
    conn.execute("""
        CREATE TABLE ORDI00F (
            NUMERO TEXT,
            DATA TEXT,
            CLIENTE TEXT,
            IMPORTO REAL
        )
    """)
    conn.execute("""
        CREATE TABLE ARTI00F (
            CODICE TEXT,
            DESCRIZIONE TEXT,
            PREZZO REAL
        )
    """)
    conn.execute("""
        CREATE TABLE MAGA00F (
            ARTICOLO TEXT,
            GIACENZA INTEGER,
            DEPOSITO TEXT
        )
    """)

    # Dati di esempio
    conn.executemany(
        "INSERT INTO ANAG00F (CODICE, RAGIONE_SOCIALE, CF, IBAN) VALUES (?, ?, ?, ?)",
        [
            ("C001", "Acme S.r.l.", "RSSMRA80A01H501U", "IT60X0542811101000000123456"),
            ("C002", "Beta S.p.A.", "GLLGNN85B02F205X", None),
            ("C003", "Gamma S.r.l.", "BNCGRD90C03F205A", "IT40X0542811101000000999999"),
        ],
    )
    conn.executemany(
        "INSERT INTO FORN00F (CODICE, RAGIONE_SOCIALE, PIVA, IBAN) VALUES (?, ?, ?, ?)",
        [
            ("F001", "Fornitore Alpha", "12345678901", "IT60X0542811101000000111111"),
            ("F002", "Fornitore Beta", "10987654321", None),
        ],
    )
    conn.executemany(
        "INSERT INTO F001 (NUMERO, DATA, CLIENTE, IMPORTO) VALUES (?, ?, ?, ?)",
        [
            ("F2024-001", "2024-01-15", "C001", 1500.00),
            ("F2024-002", "2024-02-20", "C002", 3200.50),
        ],
    )
    conn.executemany(
        "INSERT INTO ORDI00F (NUMERO, DATA, CLIENTE, IMPORTO) VALUES (?, ?, ?, ?)",
        [
            ("O2024-001", "2024-01-10", "C001", 800.00),
        ],
    )
    conn.executemany(
        "INSERT INTO ARTI00F (CODICE, DESCRIZIONE, PREZZO) VALUES (?, ?, ?)",
        [
            ("ART001", "Prodotto Alpha", 25.50),
            ("ART002", "Prodotto Beta", 120.00),
        ],
    )
    conn.executemany(
        "INSERT INTO MAGA00F (ARTICOLO, GIACENZA, DEPOSITO) VALUES (?, ?, ?)",
        [
            ("ART001", 100, "DEP01"),
            ("ART002", 50, "DEP01"),
        ],
    )

    conn.commit()
    conn.close()

    print(f"Database creato: {DB_PATH}")
    print()
    print("Per usarlo con il server MCP:")
    print(f'  export ITALY_LEGACY_DB_URL="sqlite:///{DB_PATH}"')
    print("  python -m app.server")
    print()
    print("Oppure da questa directory:")
    print(f'  export ITALY_LEGACY_DB_URL="sqlite:///$(pwd)/data/legacy.db"')


if __name__ == "__main__":
    main()
