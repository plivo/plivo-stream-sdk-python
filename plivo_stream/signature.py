"""Validation of the X-Plivo-Signature-V3 header sent on stream WebSocket connections"""

import base64
import hashlib
import hmac
from typing import Any, Iterable, Mapping, Optional
from urllib.parse import parse_qs, quote, unquote, urlparse, urlsplit

SIGNATURE_HEADER = "x-plivo-signature-v3"
NONCE_HEADER = "x-plivo-signature-v3-nonce"


def canonical_stream_url(url: str) -> str:
    """
    Return the string Plivo signs for a stream URL: scheme://host[:port], the
    URL-decoded path, then the decoded query sorted by key as k=v pairs joined
    with "&" (first value of a repeated key, not re-encoded). The fragment is dropped.
    """
    parts = urlsplit(url)
    canonical = f"{parts.scheme}://{parts.netloc}{unquote(parts.path)}"
    query = parse_qs(parts.query, keep_blank_values=True)
    pairs = [f"{key}={query[key][0]}" for key in sorted(query)]
    if pairs:
        canonical += "?" + "&".join(pairs)
    return canonical


def legacy_stream_url(url: str) -> str:
    """Return the legacy signed form of a stream URL: http://host[:port]/path, query dropped."""
    parts = urlsplit(url)
    # Parsed as http, so ";params" after the last path segment are not part of the path.
    return f"http://{parts.netloc}{urlparse(f'http://{parts.netloc}{parts.path}').path}"


def compute_signature(signed_url: str, nonce: str, auth_token: str) -> str:
    """Return base64(HMAC-SHA256(auth_token, signed_url + "." + nonce))."""
    digest = hmac.new(
        auth_token.encode("utf-8"),
        f"{signed_url}.{nonce}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def _header(headers: Any, name: str) -> Optional[str]:
    # Case-insensitive lookup that works for dicts, Starlette and websockets headers.
    items: Iterable = headers.raw_items() if hasattr(headers, "raw_items") else headers.items()
    for key, value in items:
        if key.lower() == name:
            return value
    return None


def _with_root_variants(url: str) -> list[str]:
    # A request for a URL configured without a path arrives with path "/", but
    # Plivo signs such a URL without the slash, so try both forms.
    parts = urlsplit(url)
    if parts.path not in ("", "/"):
        return [url]
    return [parts._replace(path="").geturl(), parts._replace(path="/").geturl()]


def validate_stream_signature(
    url: str,
    headers: Mapping[str, str],
    auth_token: str,
    allow_legacy_signature: bool = True,
) -> bool:
    """
    Validate the X-Plivo-Signature-V3 header of a stream WebSocket connection.

    Args:
        url: The stream URL the connection was made to, as configured in your
            <Stream> XML, e.g. "wss://example.com/stream?id=1". Path and query
            may be percent-encoded.
        headers: The connection's request headers. Must contain
            X-Plivo-Signature-V3 and X-Plivo-Signature-V3-Nonce (any case).
            The signature header may hold several comma-separated signatures.
        auth_token: Your Plivo auth token.
        allow_legacy_signature: Also accept the legacy signed form
            (http://host/path, query dropped). Transitional; it will be
            removed in a future release.

    Returns:
        True if any signature in the header matches.
    """
    if not auth_token:
        raise ValueError("auth_token is required")

    signature_header = _header(headers, SIGNATURE_HEADER)
    nonce = _header(headers, NONCE_HEADER)
    if not signature_header or not nonce:
        return False

    urls = _with_root_variants(url)
    candidates = [canonical_stream_url(u) for u in urls]
    if allow_legacy_signature:
        candidates += [legacy_stream_url(u) for u in urls]

    expected = [
        compute_signature(candidate, nonce, auth_token).encode("ascii")
        for candidate in dict.fromkeys(candidates)
    ]
    for provided in signature_header.split(","):
        provided_bytes = provided.strip().encode("utf-8")
        if any(hmac.compare_digest(provided_bytes, e) for e in expected):
            return True
    return False


def stream_url_from_scope(scope: Mapping[str, Any], public_url: Optional[str] = None) -> str:
    """
    Rebuild the stream URL Plivo connected to from an ASGI WebSocket scope.

    If public_url is set (e.g. "wss://example.com"), the request path and query
    are appended to it. Otherwise the URL is built from the Host header, using
    wss if x-forwarded-proto is https or wss (ws for any other value) and, when
    that header is absent, the scope's own scheme.
    """
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}

    if public_url:
        base = public_url.rstrip("/")
    else:
        forwarded = headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
        if forwarded:
            scheme = "wss" if forwarded in ("https", "wss") else "ws"
        else:
            scheme = "wss" if scope.get("scheme") in ("https", "wss") else "ws"
        host = headers.get("host")
        if not host and scope.get("server"):
            server_host, server_port = scope["server"]
            host = f"{server_host}:{server_port}" if server_port else server_host
        base = f"{scheme}://{host or ''}"

    raw_path = scope.get("raw_path")
    path = raw_path.decode("latin-1") if raw_path else quote(scope.get("path", "/"))
    query = scope.get("query_string", b"").decode("latin-1")
    return f"{base}{path}?{query}" if query else f"{base}{path}"
