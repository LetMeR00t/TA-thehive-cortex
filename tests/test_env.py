import requests
import os
import certifi
from test_helper import TestContext

# Initialize test context
ctx = TestContext()

print(f'REQUESTS_CA_BUNDLE: {os.environ.get("REQUESTS_CA_BUNDLE")}')
print(f'CURL_CA_BUNDLE: {os.environ.get("CURL_CA_BUNDLE")}')
print(f'Certifi location: {certifi.where()}')

ca_path = ctx.get_ca_path()
url = f"{ctx.get_thehive_url()}/api/v1/user/current"
api_key = ctx.get_thehive_api_key()
headers = {'Authorization': f'Bearer {api_key}'}

print(f'\nTesting with verify={ca_path}')
try:
    r = requests.get(url, headers=headers, verify=ca_path, timeout=10)
    print(f'Success! Status: {r.status_code}')
except Exception as e:
    print(f'Failed: {e}')
