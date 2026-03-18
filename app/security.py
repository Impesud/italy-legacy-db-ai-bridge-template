"""
Security middleware: mask sensitive strings in query results.

Applies masking to values that look like Italian Codice Fiscale (CF) or IBAN,
to reduce risk of leaking PII in logs or AI context.
"""

import re
from typing import Any

# Codice Fiscale: 16 chars, pattern AAAAAA00A00A000A (letters and digits)
_CF_PATTERN = re.compile(
    r"\b[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]\b",
    re.IGNORECASE,
)

# IBAN: IT + 2 digits + 1 letter + 10 digits + 12 alphanumeric (CIN, ABI, CAB, conto)
# Generic: 2 letters + 2 digits + 1-4 letters/digits + 11-30 alphanumeric
_IBAN_PATTERN = re.compile(
    r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7,18}[A-Z0-9]{0,4}\b",
    re.IGNORECASE,
)

MASK_PLACEHOLDER_CF = "***CF***"
MASK_PLACEHOLDER_IBAN = "***IBAN***"
MASK_PLACEHOLDER_GENERIC = "[RISERVATO]"


def _mask_cf(value: str) -> str:
    """Replace every CF-like substring with placeholder."""
    return _CF_PATTERN.sub(MASK_PLACEHOLDER_CF, value)


def _mask_iban(value: str) -> str:
    """Replace every IBAN-like substring with placeholder."""
    return _IBAN_PATTERN.sub(MASK_PLACEHOLDER_IBAN, value)


def mask_sensitive(value: str) -> str:
    """
    Mask Codice Fiscale and IBAN occurrences in a string.

    :param value: Raw string (e.g. cell value or concatenated text).
    :return: String with CF and IBAN replaced by placeholders.
    """
    if not isinstance(value, str) or not value:
        return value
    return _mask_iban(_mask_cf(value))


def mask_sensitive_data(text: str) -> str:
    """
    Funzione \"selling point\" per aziende italiane: masking PII su testo libero.

    Maschera tutte le sottostringhe che sembrano:
    - Codice Fiscale italiano
    - IBAN (formato generico, incluse varianti IT)

    Restituisce il testo con sostituzione standard: \"[RISERVATO]\".
    """
    if not isinstance(text, str) or not text:
        return text
    masked = _CF_PATTERN.sub(MASK_PLACEHOLDER_GENERIC, text)
    masked = _IBAN_PATTERN.sub(MASK_PLACEHOLDER_GENERIC, masked)
    return masked


def mask_row(row: dict[str, Any]) -> dict[str, Any]:
    """
    Apply masking to all string values in a row dict (e.g. one result row).

    :param row: Dict of column name -> value.
    :return: New dict with string values masked; non-strings unchanged.
    """
    return {
        k: mask_sensitive(v) if isinstance(v, str) else v
        for k, v in row.items()
    }


def mask_result(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Apply masking to every row in a query result list.

    :param rows: List of row dicts from a read query.
    :return: New list of row dicts with PII-like strings masked.
    """
    return [mask_row(row) for row in rows]
