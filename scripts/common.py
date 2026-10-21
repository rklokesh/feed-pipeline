"""Shared HTTP helpers for the SarkariChart watcher.

Many Indian government sites serve an incomplete certificate chain (the
"intermediate" certificate is missing). Browsers quietly fetch it; Python
does not. `get()` repairs this securely: it downloads the missing
intermediate from the address the certificate itself names (AIA), then
verifies the full chain normally. Verification is never switched off.
"""
from __future__ import annotations

import os
import ssl
import tempfile
import time
from urllib.parse import urlparse

import certifi
import requests

USER_AGENT = "SarkariChartBot/0.2 (+https://sarkarichart.com/bot; job-alert indexer)"
TIMEOUT = int(os.environ.get("FETCH_TIMEOUT", "30"))

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8"})

_bundles: dict[str, str] = {}  # host -> CA bundle path with repaired chain
last_repair_error: dict[str, str] = {}  # host -> why chain repair failed (for health.json)


def _load_any_cert(raw: bytes):
    """AIA links serve DER, PEM or PKCS#7 (.p7c) — accept all three."""
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import pkcs7

    for loader in (x509.load_der_x509_certificate, x509.load_pem_x509_certificate):
        try:
            return loader(raw)
        except ValueError:
            pass
    for loader in (pkcs7.load_der_pkcs7_certificates, pkcs7.load_pem_pkcs7_certificates):
        try:
            certs = loader(raw)
            if certs:
                return certs[0]
        except ValueError:
            pass
    raise ValueError(f"unrecognised certificate format ({raw[:20]!r})")


def _aia_bundle(host: str) -> str | None:
    """Build a CA bundle containing certifi roots + intermediates fetched via AIA."""
    if host in _bundles:
        return _bundles[host]
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives.serialization import Encoding
        from cryptography.x509.oid import AuthorityInformationAccessOID, ExtensionOID

        pem = ssl.get_server_certificate((host, 443), timeout=TIMEOUT)
        cert = x509.load_pem_x509_certificate(pem.encode())
        extra: list[bytes] = []
        for _ in range(3):  # walk up to three intermediates
            try:
                aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
            except x509.ExtensionNotFound:
                break
            urls = [d.access_location.value for d in aia if d.access_method == AuthorityInformationAccessOID.CA_ISSUERS]
            if not urls:
                break
            raw = requests.get(urls[0], timeout=TIMEOUT).content
            cert = _load_any_cert(raw)
            extra.append(cert.public_bytes(Encoding.PEM))
            if cert.issuer == cert.subject:
                break
        if not extra:
            last_repair_error[host] = "certificate has no AIA issuer link"
            return None
        fd, path = tempfile.mkstemp(suffix=".pem")
        with os.fdopen(fd, "wb") as f:
            f.write(open(certifi.where(), "rb").read())
            for e in extra:
                f.write(b"\n" + e)
        _bundles[host] = path
        return path
    except Exception as e:  # noqa: BLE001
        last_repair_error[host] = f"{type(e).__name__}: {e}"[:200]
        return None


def get(url: str, attempts: int = 3, stream: bool = False) -> requests.Response:
    """GET with polite retries/back-off and certificate-chain repair. Raises on final failure."""
    last: Exception | None = None
    host = urlparse(url).hostname or ""
    for i in range(1, attempts + 1):
        try:
            verify = _bundles.get(host, True)
            return session.get(url, timeout=TIMEOUT, stream=stream, verify=verify)
        except requests.exceptions.SSLError as e:
            last = e
            bundle = _aia_bundle(host)
            if bundle:
                try:
                    return session.get(url, timeout=TIMEOUT, stream=stream, verify=bundle)
                except requests.RequestException as e2:
                    last = e2
                    last_repair_error[host] = f"chain repaired but still failing: {e2}"[-200:]
            break  # a real certificate problem: don't hammer the site
        except requests.RequestException as e:
            last = e
            time.sleep(2 ** i)  # official sites are often overloaded
    assert last is not None
    raise last


def download(url: str, max_bytes: int = 15 * 1024 * 1024, referer: str = "") -> bytes:
    if referer:
        session.headers["Referer"] = referer  # some boards (ASP.NET) only serve files to their own pages
    try:
        r = get(url, stream=True)
    finally:
        session.headers.pop("Referer", None)
    r.raise_for_status()
    data = b""
    for chunk in r.iter_content(64 * 1024):
        data += chunk
        if len(data) > max_bytes:
            break
    return data
