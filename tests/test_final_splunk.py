import requests
import sys
import os
from test_helper import TestContext

# Initialize test context
ctx = TestContext()

ca_path = ctx.get_ca_path()
url = f"{ctx.get_thehive_url()}/api/v1/user/current"
api_key = ctx.get_thehive_api_key()
headers = {'Authorization': f'Bearer {api_key}'}
try:
    print(f'Testing with verify={ca_path}')
    r = requests.get(url, headers=headers, verify=ca_path, timeout=10)
    print(f'Success! Status: {r.status_code}')
except Exception as e:
    print(f'Failed with CA cert: {e}')

try:
    print('\nTesting with verify=False (Insecure)')
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    r = requests.get(url, headers=headers, verify=False, timeout=10)
    print(f'Success (Insecure)! Status: {r.status_code}')
except Exception as e:
    print(f'Failed even without verify: {e}')
