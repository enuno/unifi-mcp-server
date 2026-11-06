"""Turn ``Settings.verify_ssl`` into the ``verify=`` argument httpx expects."""

import ssl
from collections.abc import Awaitable, Callable
from functools import lru_cache

import httpx

RequestHook = Callable[[httpx.Request], Awaitable[None]]


@lru_cache(maxsize=16)
def _context_for(ca_file: str) -> ssl.SSLContext:
    # Only ``ca_file`` is trusted, as for UNIFI_AUDIT_SIEM_CA_FILE (src/utils/siem.py).
    context = ssl.create_default_context(cafile=ca_file)
    # Python 3.13 made default contexts strict (VERIFY_X509_STRICT). Its RFC 5280
    # profile checks reject the certificate UniFi OS generates for itself, whose Key
    # Usage includes keyCertSign without Basic Constraints, as "invalid CA certificate",
    # so a console's own certificate could not be used here. This file is the only
    # trust anchor; the chain, signature, validity and name are still checked.
    context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return context


def httpx_verify(verify: bool | str) -> bool | ssl.SSLContext:
    """Return ``verify`` unchanged when it is a bool, or an SSL context for a CA bundle path.

    httpx 0.28 deprecates ``verify=<path>``, so a CA bundle becomes a context.
    Contexts are cached per path: clients are built per tool call.
    """
    if isinstance(verify, str):
        return _context_for(verify)
    return verify


def tls_event_hooks(server_name: str | None) -> dict[str, list[RequestHook]]:
    """Return httpx ``event_hooks`` that check the certificate against ``server_name``.

    httpx sends a request's ``sni_hostname`` extension as SNI and checks the
    certificate against it in place of the URL's host. Without a name, no hooks.
    """
    if not server_name:
        return {}

    async def check_server_name(request: httpx.Request) -> None:
        request.extensions["sni_hostname"] = server_name

    return {"request": [check_server_name]}
