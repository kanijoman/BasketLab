"""The one text normaliser for person and club names (#1128): the leagues write the same name with accents, apostrophes (``'``, ``´``, ``’``) and letters NFKD does not decompose (Ł, Ø, ß, ı)."""
from __future__ import annotations

import unicodedata
from typing import Any, List

# NFKD leaves these letters whole; the case is kept (``plain_words`` upper-cases first, where ``ß`` is already ``SS``)
_SPECIAL = str.maketrans({"Ł": "L", "ł": "l", "Ø": "O", "ø": "o", "ß": "ss", "ı": "i", "Đ": "D", "đ": "d", "Æ": "AE", "æ": "ae", "Œ": "OE", "œ": "oe"})


def strip_accents(text: Any) -> str:
    """The text without accents or marks (case kept); ``Ł Ø ß ı`` become their plain letters."""
    return "".join(c for c in unicodedata.normalize("NFKD", str(text or "").translate(_SPECIAL)) if not unicodedata.combining(c))


def plain_words(text: Any) -> List[str]:
    """Upper-case words without accents: every sign that is not a letter or a digit (dots, hyphens, apostrophes, commas) separates words."""
    stripped = strip_accents(str(text or "").upper())
    return "".join(c if c.isalnum() else " " for c in stripped).split()
