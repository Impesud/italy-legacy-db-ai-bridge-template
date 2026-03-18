## Security & GDPR posture (Italy Legacy DB AI Bridge)

Documento breve per **IT/Security/Compliance**: descrive i controlli implementati per ridurre il rischio di esposizione di dati personali (GDPR) durante l’uso di Claude tramite MCP.

### Scopo

- Consentire interrogazioni a sistemi legacy (AS/400, SQL Server) **in sola lettura**
- Ridurre il rischio di leakage di PII tramite **masking** e **assenza di retention**
- Fornire un meccanismo di **audit minimale** (report di pulizia) senza loggare dati

---

### Controlli implementati (by design)

- **Read-only enforcement**
  - Il connector rifiuta SQL non read-only: solo `SELECT`/`WITH`/`PRAGMA`/`EXPLAIN`… (`app/connector.py`, `_assert_read_only_sql()`).
  - La sessione **non esegue commit**: chiude sempre con `rollback()` (difesa contro scritture accidentali).
  - Raccomandazione: in produzione usare anche ruoli DB **read-only** (controllo “server-side”).

- **Anti-injection (identificatori)**
  - I nomi di tabella/colonna ammessi sono limitati a `[A-Za-z0-9_]` (`app/server.py`, `_safe_identifier()`).
  - I valori passano come bind parameters (`:p_xxx`) e non vengono interpolati nella SQL.

- **PII Masking (default)**
  - I risultati della query vengono mascherati per pattern:
    - **Codice Fiscale** (16 caratteri)
    - **IBAN**
  - Masking a livello di risultato: `mask_result()` (`app/security.py`)
  - Masking “testo libero” (selling point): `mask_sensitive_data(text)` → placeholder **`[RISERVATO]`**

- **No retention / pulizia privacy**
  - Tool MCP: **`privacy_cleanup`** chiude connessioni/pool e resetta stato interno; restituisce un report (timestamp, `connections_closed`, `state_reset`).
  - Opzionale: pulizia automatica post-query via env `ITALY_LEGACY_PRIVACY_AUTO_CLEANUP=1` (chiusura e reset dopo ogni `query_legacy_db`).
  - Obiettivo: minimizzare la permanenza in memoria di dati sensibili lato server.

---

### Configurazioni consigliate (produzione)

- **DB account read-only**: permessi di sola lettura sulle tabelle necessarie.
- **Limit e minimizzazione**: usare `limit` e filtri per ridurre il volume di dati.
- **Mapping semantico controllato**: mantenere `mapping.json` (o `ITALY_LEGACY_MAPPING_PATH`) come whitelist logica delle tabelle esposte.
- **Auto-cleanup**: abilitare `ITALY_LEGACY_PRIVACY_AUTO_CLEANUP=1` in ambienti ad alta sensibilità.

---

### Audit / evidenze

- **Report di pulizia**: `privacy_cleanup` produce un output strutturato utilizzabile come evidenza operativa (senza contenuti PII).
- **Validazione funzionale (demo)**: vedere README “Validazione (risultati attesi con Claude)”.

---

### Cosa NON fa (scope limitato)

- Non sostituisce un DLP aziendale completo.
- Non implementa cifratura a riposo (dipende dal DB/storage).
- Non implementa RBAC applicativo multi-tenant (assunto: server locale per singola integrazione).
- Non effettua classificazione semantica del contenuto (oltre ai pattern CF/IBAN).

Se servono requisiti enterprise (RBAC, audit log firmati, allowlist colonne, data lineage), possiamo estendere il bridge in modo compatibile MCP.

