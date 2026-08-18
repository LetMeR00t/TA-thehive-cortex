import sys
import os
from test_helper import TestContext
import json

# Initialize test context
ctx = TestContext()

from splunk.rest import simpleRequest

# Connect to Splunk
spl = ctx.get_splunk_service()
token = spl.token

url = 'https://localhost:8089/services/storage/passwords?output_mode=json'
try:
    resp, content = simpleRequest(url, sessionKey=token, method='GET', raiseAllErrors=True)
    print(f'REST Status: {resp.status}')
    data = json.loads(content)
    for entry in data.get('entry', []):
        print(f"Entry: realm={entry['content'].get('realm')}, user={entry['content'].get('username')}")
except Exception as e:
    print(f'REST Failed: {e}')
