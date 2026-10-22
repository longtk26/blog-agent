import re
import unicodedata

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "})
_ELLIPSIS = re.compile(r"\s*(?:\.\.\.|…)\s*")


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_QUOTES).lower()
    return " ".join(text.split())


def quote_in_text(quote: str, text: str | None) -> bool:
    """True if the (whitespace/quote-normalised) quote appears verbatim in the page text.
    Quotes elided with '...' must have every fragment present, in order."""
    if not quote or not text:
        return False
    haystack = _normalize(text)
    position = 0
    fragments = [f for f in (_normalize(p).strip(" \"'") for p in _ELLIPSIS.split(quote)) if f]
    if not fragments or sum(len(f) for f in fragments) < 12:
        return False
    for fragment in fragments:
        found = haystack.find(fragment, position)
        if found < 0:
            return False
        position = found + len(fragment)
    return True
