"""
Semantic Mapper: translates logical table names (AI-friendly) to physical legacy names.

Loads mapping from config/mapping.json so that e.g. 'Anagrafica_Clienti' -> 'ANAG00F'.
"""

import json
import os
from pathlib import Path
from typing import Optional

# Default path relative to package root; can be overridden via env or constructor
DEFAULT_MAPPING_PATH = Path(__file__).resolve().parent.parent / "config" / "mapping.json"


def _resolve_mapping_path(override: Optional[Path] = None) -> Path:
    """Resolve mapping file path: env ITALY_LEGACY_MAPPING_PATH > override > default."""
    if override is not None:
        return override
    env_path = os.environ.get("ITALY_LEGACY_MAPPING_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_MAPPING_PATH


class SemanticMapper:
    """
    Maps logical (semantic) table names to physical table names used in legacy systems.

    Used so that the AI can ask for 'Anagrafica_Clienti' while the database
    actually uses 'ANAG00F' (AS/400-style naming).
    """

    def __init__(self, mapping_path: Optional[Path] = None) -> None:
        """
        Load mapping from JSON config.

        :param mapping_path: Path to mapping.json. If None, uses ITALY_LEGACY_MAPPING_PATH
                             env var or config/mapping.json next to the project root.
        """
        self._path = _resolve_mapping_path(mapping_path)
        self._logical_to_physical: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        """Load mapping from config file."""
        if not self._path.exists():
            self._logical_to_physical = {}
            return
        with open(self._path, encoding="utf-8") as f:
            data = json.load(f)
        # Support both { "tables": { "Logical": "PHYSICAL" } } and flat { "Logical": "PHYSICAL" }
        if "tables" in data:
            self._logical_to_physical = {k: v for k, v in data["tables"].items()}
        else:
            self._logical_to_physical = {k: v for k, v in data.items() if isinstance(v, str)}

    def to_physical(self, logical_name: str) -> str:
        """
        Resolve logical table name to physical table name.

        If the logical name is not in the mapping, it is returned unchanged
        (allowing direct physical names to be passed through).

        :param logical_name: Human-readable table name (e.g. 'Anagrafica_Clienti').
        :return: Physical table name (e.g. 'ANAG00F').
        """
        key = logical_name.strip()
        return self._logical_to_physical.get(key, key)

    def list_logical_names(self) -> list[str]:
        """Return all known logical table names."""
        return list(self._logical_to_physical.keys())

    def reload(self) -> None:
        """Reload mapping from disk (e.g. after config change)."""
        self._load()
