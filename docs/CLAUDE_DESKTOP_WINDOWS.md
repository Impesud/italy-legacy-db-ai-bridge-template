# Collegare il bridge a Claude Desktop su Windows

Due modalità:

- **A (consigliata)**: progetto + DB su Windows
- **B**: progetto + DB in WSL, Claude Desktop su Windows avvia via `wsl`

## A) Tutto su Windows (consigliato)

### Setup (PowerShell)

```powershell
cd C:\Path\To\italy-legacy-db-ai-bridge-template
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
# ODBC: pip install -e ".[dev,odbc]"
python scripts/create_demo_db.py
```

### Config Claude Desktop

File: `%APPDATA%\Claude\claude_desktop_config.json`

Esempio minimo:

```json
{
  "mcpServers": {
    "italy-legacy-db": {
      "command": "C:\\\\Path\\\\To\\\\italy-legacy-db-ai-bridge-template\\\\.venv\\\\Scripts\\\\python.exe",
      "args": ["-m", "app.server"],
      "env": {
        "ITALY_LEGACY_DB_URL": "sqlite:///C:/Path/To/italy-legacy-db-ai-bridge-template/data/legacy.db"
      }
    }
  }
}
```

Poi **riavvia** Claude Desktop (uscita completa + riapertura) e verifica che compaiano i tool `query_legacy_db` e `privacy_cleanup`.

## B) Progetto in WSL, Claude Desktop su Windows

Usa quando vuoi tenere progetto/DB in WSL.

Config consigliata (robusta: esporta `ITALY_LEGACY_DB_URL` inline):

```json
{
  "mcpServers": {
    "italy-legacy-db": {
      "command": "wsl",
      "args": [
        "-d",
        "Ubuntu",
        "-e",
        "bash",
        "-lc",
        "export ITALY_LEGACY_DB_URL='sqlite:////ABSOLUTE/PATH/TO/data/legacy.db'; cd /ABSOLUTE/PATH/TO/PROJECT && exec .venv/bin/python -m app.server"
      ]
    }
  }
}
```

Nota: sostituisci `Ubuntu` con la distro reale (`wsl -l -v`).

## Prova in chat

- “Elenca 5 righe da **Anagrafica_Clienti**”
- “Trova le **Fatture** del cliente **<CODICE_CLIENTE>**”
- “Esegui **privacy_cleanup** e mostrami il report”

### Risultati attesi

- `Anagrafica_Clienti`: un set di righe coerente con il tuo gestionale; CF/IBAN risultano **mascherati**.
- `Fatture` filtrate per cliente: un set di righe coerente con il tuo gestionale.
- `privacy_cleanup`: report con `connections_closed=true` e `state_reset=true`.

## Troubleshooting rapido

- **Tool non compaiono**: path `command` sbagliato o Claude non riavviato.
- **No such table**: `ITALY_LEGACY_DB_URL` punta a DB vuoto/in-memory.
- **WSL path non trovato**: stai usando la distro sbagliata → aggiungi `-d Ubuntu`.
