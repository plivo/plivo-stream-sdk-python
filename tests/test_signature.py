import asyncio

import pytest
from starlette.websockets import WebSocket

from plivo_stream import PlivoFastAPIStreamingHandler, validate_stream_signature
from plivo_stream.signature import canonical_stream_url, compute_signature

TOKEN = "test-auth-token"
NONCE = "12345678901234567890"

# (stream URL as configured, string Plivo signs before "." + nonce, signature)
VECTORS = [
    ("wss://example.com/media/stream?tenant=42&env=prod", "wss://example.com/media/stream?env=prod&tenant=42", "Ni6eSQI9zg/LjUt95Nlt5nTYA7FpL6CQuY2F+Yy3jyc="),
    ("ws://example.com/media/stream?tenant=42&env=prod", "ws://example.com/media/stream?env=prod&tenant=42", "De3cjnXuPrS4pSTyrva6wFEYh9CpRgvlyaQ1gct9auo="),
    ("wss://example.com/media/stream", "wss://example.com/media/stream", "paNuAIW+AAlyCT4lFH8ZrCvzj3gkNuvrX0r877mN3nM="),
    ("wss://example.com:8443/ws/?b=2&a=1", "wss://example.com:8443/ws/?a=1&b=2", "d4mqJrd9gtwO+Dfc7IT4u144WmmoPrnCjYUTmM3HBSk="),
    ("wss://example.com/s?sig=abc%3D%3D&name=John+Doe", "wss://example.com/s?name=John Doe&sig=abc==", "WkbN9mLc0kqBHtOjlD4GiUIvDkZ+cSfqUsEKrF8ixmY="),
    ("wss://example.com/s?a=2&a=1&b=", "wss://example.com/s?a=2&b=", "2cKu0gQz5RJiYNmM0R6KIxu2Wphx3qSHChoOgvNdGKo="),
    ("wss://example.com/my%20stream/ws?id=1", "wss://example.com/my stream/ws?id=1", "5hGH/IknEopkorKviPg1OTVLJvkZ/oqs3GBHF9Si4mw="),
    ("wss://example.com/s?name=Jos%C3%A9", "wss://example.com/s?name=José", "j0fffZVummAvqXtvGPkEVhnNDmDeFaTPXDP4CedUaow="),
    ("wss://example.com/s?flag&x=1", "wss://example.com/s?flag=&x=1", "EZ6eDWNK9Elkw49HS/1NHdZH/ItKIISoqPVbfhgM7tE="),
    ("wss://example.com/media/stream?", "wss://example.com/media/stream", "paNuAIW+AAlyCT4lFH8ZrCvzj3gkNuvrX0r877mN3nM="),
    ("wss://example.com/media/stream#frag", "wss://example.com/media/stream", "paNuAIW+AAlyCT4lFH8ZrCvzj3gkNuvrX0r877mN3nM="),
    ("wss://example.com", "wss://example.com", "mXPltZtATpEE0xZ2FUiuVHgIis/d14y8t/rtESnFGjU="),
    ("wss://example.com/a%2Fb/ws?q=1", "wss://example.com/a/b/ws?q=1", "ZnGd8sbUoc4m+gsJK4smUKQF51bEy5S2dSEYnS/FZdc="),
]

# Legacy form of VECTORS[0]: http://example.com/media/stream
LEGACY_SIG = "OsoXE2Y6C/OkM6NFun7zqG99JK4Si+8genxgF2bWtzc="


def sig_headers(signature, nonce=NONCE):
    return {"X-Plivo-Signature-V3": signature, "X-Plivo-Signature-V3-Nonce": nonce}


@pytest.mark.parametrize("url,signed,sig", VECTORS)
def test_vectors(url, signed, sig):
    assert canonical_stream_url(url) == signed
    assert compute_signature(signed, NONCE, TOKEN) == sig
    assert validate_stream_signature(url, sig_headers(sig), TOKEN, allow_legacy_signature=False)


def test_legacy_signature_follows_option():
    url = VECTORS[0][0]
    assert compute_signature("http://example.com/media/stream", NONCE, TOKEN) == LEGACY_SIG
    assert validate_stream_signature(url, sig_headers(LEGACY_SIG), TOKEN)
    assert not validate_stream_signature(url, sig_headers(LEGACY_SIG), TOKEN, allow_legacy_signature=False)


def test_legacy_signature_bare_root():
    sig = compute_signature("http://example.com", NONCE, TOKEN)
    assert validate_stream_signature("wss://example.com/", sig_headers(sig), TOKEN)


def test_bare_root_request_path():
    url, _, sig = VECTORS[11]
    assert validate_stream_signature(url + "/", sig_headers(sig), TOKEN)


def test_comma_separated_signatures():
    url, _, sig = VECTORS[0]
    other = compute_signature(VECTORS[0][1], NONCE, "other-auth-token")
    assert validate_stream_signature(url, sig_headers(f"{other},{sig}"), TOKEN)
    assert validate_stream_signature(url, sig_headers(f"{sig}, {other}"), TOKEN)
    assert not validate_stream_signature(url, sig_headers(f"{other},{other}"), TOKEN)


def test_rejects_wrong_signature_token_nonce_or_url():
    url, _, sig = VECTORS[0]
    assert not validate_stream_signature(url, sig_headers("bm90LWEtc2lnbmF0dXJl"), TOKEN)
    assert not validate_stream_signature(url, sig_headers(sig), "other-auth-token")
    assert not validate_stream_signature(url, sig_headers(sig, nonce="1"), TOKEN)
    assert not validate_stream_signature("ws://example.com/media/stream?tenant=42&env=prod", sig_headers(sig), TOKEN)
    assert not validate_stream_signature(url, sig_headers("sïg"), TOKEN)


def test_rejects_missing_headers():
    url, _, sig = VECTORS[0]
    assert not validate_stream_signature(url, {}, TOKEN)
    assert not validate_stream_signature(url, {"X-Plivo-Signature-V3": sig}, TOKEN)
    assert not validate_stream_signature(url, {"X-Plivo-Signature-V3-Nonce": NONCE}, TOKEN)


def test_header_names_are_case_insensitive():
    url, _, sig = VECTORS[0]
    headers = {"x-plivo-signature-v3": sig, "X-PLIVO-SIGNATURE-V3-NONCE": NONCE}
    assert validate_stream_signature(url, headers, TOKEN)


def test_requires_auth_token():
    with pytest.raises(ValueError):
        validate_stream_signature(VECTORS[0][0], sig_headers(VECTORS[0][2]), "")


# FastAPI handler


def run_handler(headers, path, query="", scheme="ws", **start_kwargs):
    """Run handler.start() against a Starlette WebSocket; return (accepted, errors, sent)."""
    scope = {
        "type": "websocket",
        "scheme": scheme,
        "server": ("127.0.0.1", 8000),
        "path": path,
        "raw_path": path.encode(),
        "query_string": query.encode(),
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    incoming = [{"type": "websocket.connect"}, {"type": "websocket.disconnect", "code": 1000}]
    sent = []

    async def receive():
        return incoming.pop(0)

    async def send(message):
        sent.append(message)

    handler = PlivoFastAPIStreamingHandler(WebSocket(scope, receive, send))
    errors = []

    @handler.on_error
    async def on_error(error):
        errors.append(error)

    asyncio.run(handler.start(**start_kwargs))
    accepted = any(m["type"] == "websocket.accept" for m in sent)
    return accepted, errors, [m["type"] for m in sent]


def verify(**kwargs):
    return {"with_signature_verification": True, "auth_token": TOKEN, **kwargs}


def test_handler_uses_forwarded_proto_for_wss():
    sig = VECTORS[0][2]
    headers = {"host": "example.com", "x-forwarded-proto": "https", **sig_headers(sig)}
    accepted, errors, _ = run_handler(headers, "/media/stream", "tenant=42&env=prod", **verify())
    assert accepted and not errors


def test_handler_uses_forwarded_proto_for_ws():
    sig = VECTORS[1][2]
    headers = {"host": "example.com", "x-forwarded-proto": "http", **sig_headers(sig)}
    accepted, _, _ = run_handler(headers, "/media/stream", "tenant=42&env=prod", scheme="wss", **verify())
    assert accepted


def test_handler_uses_request_scheme_without_forwarded_proto():
    headers = {"host": "example.com", **sig_headers(VECTORS[0][2])}
    accepted, _, _ = run_handler(headers, "/media/stream", "tenant=42&env=prod", scheme="wss", **verify())
    assert accepted
    accepted, errors, _ = run_handler(headers, "/media/stream", "tenant=42&env=prod", scheme="ws", **verify())
    assert not accepted and errors


def test_handler_public_url_override():
    headers = {"host": "10.0.0.5:8000", **sig_headers(VECTORS[0][2])}
    accepted, _, _ = run_handler(
        headers, "/media/stream", "tenant=42&env=prod", **verify(public_url="wss://example.com/")
    )
    assert accepted
    accepted, _, _ = run_handler(headers, "/media/stream", "tenant=42&env=prod", **verify())
    assert not accepted


def test_handler_encoded_path_and_bare_root():
    headers = {"host": "example.com", "x-forwarded-proto": "https", **sig_headers(VECTORS[12][2])}
    assert run_handler(headers, "/a%2Fb/ws", "q=1", **verify())[0]
    headers = {"host": "example.com", "x-forwarded-proto": "https", **sig_headers(VECTORS[11][2])}
    assert run_handler(headers, "/", **verify())[0]


def test_handler_legacy_signature_follows_option():
    headers = {"host": "example.com", "x-forwarded-proto": "https", **sig_headers(LEGACY_SIG)}
    assert run_handler(headers, "/media/stream", "tenant=42&env=prod", **verify())[0]
    accepted, errors, _ = run_handler(
        headers, "/media/stream", "tenant=42&env=prod", **verify(allow_legacy_signature=False)
    )
    assert not accepted and errors


def test_handler_rejects_wrong_or_missing_signature():
    headers = {"host": "example.com", "x-forwarded-proto": "https", **sig_headers(VECTORS[1][2])}
    accepted, errors, sent = run_handler(headers, "/media/stream", "tenant=42&env=prod", **verify())
    assert not accepted and str(errors[0]) == "Invalid socket signature"
    assert sent == ["websocket.close"]
    accepted, _, sent = run_handler({"host": "example.com"}, "/media/stream", **verify())
    assert not accepted and sent == ["websocket.close"]


def test_handler_without_verification_accepts():
    assert run_handler({"host": "example.com"}, "/media/stream")[0]


def test_handler_requires_auth_token():
    with pytest.raises(ValueError):
        run_handler({}, "/", with_signature_verification=True)
