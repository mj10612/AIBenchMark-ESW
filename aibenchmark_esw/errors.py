"""Credential-free, bounded diagnostics for published evaluation artifacts."""

import re


def _redact_url_query(match):
    url = match.group()
    suffix = ''
    if url.startswith("'"):
        body, quote, punctuation = url[1:].rpartition("'")
        if quote and re.fullmatch(r'[,;)}\]]*', punctuation):
            # The final quote encloses the diagnostic; earlier apostrophes
            # belong to the URL and can be part of a credential value.
            url, suffix = "'" + body, quote + punctuation
    before_fragment, fragment_separator, fragment = url.partition('#')
    base, query_separator, query = before_fragment.partition('?')
    query = re.sub(r'(?i)((?:^|&)(?:key|token)=)[^&]*', r'\1[REDACTED]', query)
    return base + query_separator + query + fragment_separator + fragment + suffix


def redact(text, secrets=()):
    text = str(text)
    for secret in secrets:
        if isinstance(secret, str) and secret:
            text = text.replace(secret, '[REDACTED]')
    text = re.sub(r'\bsk-[A-Za-z0-9_-]+', '[REDACTED]', text)
    text = re.sub(r'(?i)\bBearer\s+[^\s,;"\'<>]+', 'Bearer [REDACTED]', text)
    text = re.sub(r'(?i)(https?://)[^/\s@]+@', r'\1[REDACTED]@', text)
    text = re.sub(r'''(?i)'?https?://[^\s"<>]+''', _redact_url_query, text)
    text = re.sub(r'''(?ix)(["']?(?:api[_-]?key|access[_-]?token|authorization|password|secret)["']?\s*[:=]\s*)(?:["'][^"']*["']|[^\s,;&}\]]+)''', r'\1[REDACTED]', text)
    return text


def error_diagnostic(error, secrets=()):
    text = redact(error, secrets)
    return f'{type(error).__name__}: ' + text[:2048] + (' [truncated]' if len(text) > 2048 else '')
