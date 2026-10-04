"""Reach TheHive with each TLS protocol version forced in turn, verifying
against the app's local/cacert.crt, to find which handshake the server accepts.

    python tools/manual/diag_tls.py
"""
import ssl

import requests
from diag_helper import TestContext
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager


def make_adapter(protocol):
    class TLSAdapter(HTTPAdapter):
        def init_poolmanager(self, connections, maxsize, block=False):
            self.poolmanager = PoolManager(
                num_pools=connections,
                maxsize=maxsize,
                block=block,
                ssl_version=protocol,
            )

    return TLSAdapter()


def test_version(protocol, name, ctx):
    try:
        s = requests.Session()
        s.mount("https://", make_adapter(protocol))
        url = f"{ctx.get_thehive_url()}/api/v1/user/current"
        r = s.get(url,
                  headers={"Authorization": f"Bearer {ctx.get_thehive_api_key()}"},
                  verify=ctx.get_ca_path(), timeout=5)
        print(f"{name}: Success (Status {r.status_code})")
        print(f"   Body: {r.text[:100]}")
    except Exception as e:
        print(f"{name}: Failed - {e}")


if __name__ == "__main__":
    context = TestContext()
    print("Testing various TLS versions...")
    # Older protocols may be absent from a recent Python/OpenSSL build.
    for attr, name in (("PROTOCOL_TLSv1_1", "TLS 1.1"),
                       ("PROTOCOL_TLSv1_2", "TLS 1.2"),
                       ("PROTOCOL_TLS", "TLS (Auto/1.3)")):
        protocol = getattr(ssl, attr, None)
        if protocol is None:
            print(f"{name}: not available in this Python")
            continue
        test_version(protocol, name, context)
