import requests
import sys
import os
from test_helper import TestContext

# Initialize test context
ctx = TestContext()

try:
    api_key = ctx.get_thehive_api_key()
    url = f"{ctx.get_thehive_url()}/api/v1/user/current"
    r = requests.get(
        url, 
        headers={'Authorization': f'Bearer {api_key}'}, 
        verify=ctx.get_ca_path(),
        timeout=10
    )
    print(f'Status: {r.status_code}')
    print(f'Body: {r.text[:100]}')
except Exception as e:
    print(f'Error: {e}')
