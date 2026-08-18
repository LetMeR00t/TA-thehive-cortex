import sys
import os
from test_helper import TestContext

# Initialize test context
ctx = TestContext()

from thehive4py.client import TheHiveApi

ca_path = ctx.get_ca_path()
url = ctx.get_thehive_url()
api_key = ctx.get_thehive_api_key()

print(f'Testing TheHiveApi with verify={ca_path}')
try:
    api = TheHiveApi(url=url, apikey=api_key, verify=ca_path)
    user = api.user.get_current()
    if '_id' in user:
        print(f'Success! User ID: {user["_id"]}')
    else:
        print(f'Failed! Response: {user}')
except Exception as e:
    print(f'Exception: {e}')
