"""Reach TheHive's /api/v1/user/current with plain `requests`, verifying TLS
against the app's local/cacert.crt; with --insecure, retry without
verification to tell a CA problem from a network one.

Also prints the CA bundle environment variables and certifi's location, which
override or replace the CA file depending on how `requests` is called.

    python tools/manual/diag_conn.py [--insecure]
"""
import os
import sys

import certifi
import requests
from diag_helper import TestContext

ctx = TestContext()

print(f'REQUESTS_CA_BUNDLE: {os.environ.get("REQUESTS_CA_BUNDLE")}')
print(f'CURL_CA_BUNDLE: {os.environ.get("CURL_CA_BUNDLE")}')
print(f"Certifi location: {certifi.where()}")

url = f"{ctx.get_thehive_url()}/api/v1/user/current"
headers = {"Authorization": f"Bearer {ctx.get_thehive_api_key()}"}
ca_path = ctx.get_ca_path()

try:
    print(f"\nTesting with verify={ca_path}")
    r = requests.get(url, headers=headers, verify=ca_path, timeout=10)
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text[:100]}")
except Exception as e:
    print(f"Failed with CA cert: {e}")

if "--insecure" in sys.argv[1:]:
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        print("\nTesting with verify=False (Insecure)")
        r = requests.get(url, headers=headers, verify=False, timeout=10)
        print(f"Success (Insecure)! Status: {r.status_code}")
    except Exception as e:
        print(f"Failed even without verify: {e}")
