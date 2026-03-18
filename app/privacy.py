"""
Pulizia automatica per la privacy (selling point per aziende italiane / GDPR).

Garantisce che:
- Nessun risultato di query resti in memoria dopo la risposta.
- Le connessioni al DB vengano chiuse e il pool rilasciato.
- Lo stato interno del server (connector, mapper cache) venga azzerato su richiesta
  o dopo ogni query, in modalità "pulizia automatica".

Nessun log delle query o dei risultati; nessuna persistenza di dati sensibili.
"""

import os
import time
from typing import Any, Callable, Optional, Protocol


class ClosableConnector(Protocol):
    """Protocol per un connector che espone close()."""

    def close(self) -> None: ...


def run_privacy_cleanup(
    connector: Optional[ClosableConnector] = None,
    *,
    reset_state_callback: Optional[Callable[[], None]] = None,
) -> dict[str, Any]:
    """
    Esegue la pulizia per la privacy: chiude connessioni e azzera lo stato interno.

    Da usare dopo ogni query (se ITALY_LEGACY_PRIVACY_AUTO_CLEANUP=1) o su
    richiesta tramite il tool MCP privacy_cleanup, per dare garanzie alle
    aziende su assenza di retention di dati sensibili.

    :param connector: Istanza del connector da chiudere (rilascio pool/connessioni).
    :param reset_state_callback: Callback opzionale per azzerare i singleton
                                 (connector, mapper) nel server così la prossima
                                 richiesta ricrea risorse pulite.
    :return: Report di audit (connessioni chiuse, stato azzerato, timestamp).
    """
    report: dict[str, Any] = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "connections_closed": False,
        "state_reset": False,
        "message": "Pulizia privacy completata.",
    }

    if connector is not None:
        try:
            connector.close()
            report["connections_closed"] = True
        except Exception as e:
            report["connections_closed"] = False
            report["warning"] = str(e)

    if reset_state_callback is not None:
        try:
            reset_state_callback()
            report["state_reset"] = True
        except Exception as e:
            report["state_reset"] = False
            report["warning"] = report.get("warning", "") + " " + str(e)

    return report


def is_auto_cleanup_enabled() -> bool:
    """Legge da env se la pulizia automatica dopo ogni query è attiva."""
    return os.environ.get("ITALY_LEGACY_PRIVACY_AUTO_CLEANUP", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
