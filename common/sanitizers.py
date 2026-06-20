import re

import bleach

_SCRIPT_RE = re.compile(r'<script[\s\S]*?</script>', re.IGNORECASE)
_STYLE_RE = re.compile(r'<style[\s\S]*?</style>', re.IGNORECASE)


def sanitize_text(value: str | None) -> str | None:
    """
    Strip all HTML/script from user-provided free text to prevent XSS.
    Dangerous tag contents (script, style) are removed entirely;
    remaining tags are stripped while preserving their text content.
    """
    if value is None:
        return None
    text = str(value)
    text = _SCRIPT_RE.sub('', text)
    text = _STYLE_RE.sub('', text)
    return bleach.clean(text, tags=[], attributes={}, strip=True)
