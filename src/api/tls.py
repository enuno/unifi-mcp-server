"""Turn ``Settings.verify_ssl`` into the ``verify=`` argument httpx expects."""

import ssl
from functools import lru_cache


@lru_cache(maxsize=16)
def _context_for(ca_file: str) -> ssl.SSLContext:
    # Only ``ca_file`` is trusted, as for UNIFI_AUDIT_SIEM_CA_FILE (src/utils/siem.py).
    return ssl.create_default_context(cafile=ca_file)


def httpx_verify(verify: bool | str) -> bool | ssl.SSLContext:
    """Return ``verify`` unchanged when it is a bool, or an SSL context for a CA bundle path.

    httpx 0.28 deprecates ``verify=<path>``, so a CA bundle becomes a context.
    Contexts are cached per path: clients are built per tool call.
    """
    if isinstance(verify, str):
        return _context_for(verify)
    return verify
