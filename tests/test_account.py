import sys
import os
from test_helper import TestContext

# Initialize test context
ctx = TestContext()

from common import Settings, LoggerFile
from ta_logging import setup_logging

logger = setup_logging('script')
logger_file = LoggerFile(logger, 'TEST')

# Connect to Splunk
spl = ctx.get_splunk_service()

configuration = Settings(spl, None, logger_file)
# Recover accounts
accounts = configuration.getAccounts()
print(f'Accounts found: {list(accounts.keys())}')

if 'local' in accounts:
    # Use the method from Settings class
    user, secret = configuration.getInstanceUsernameApiKey('Org L2')
    print(f'Org L2 -> User: {user}, Secret length: {len(secret)}')
    # Check if secret matches known API Key
    expected = ctx.get_thehive_api_key()
    if secret == expected:
        print('API Key is CORRECT')
    else:
        print(f'API Key is INCORRECT. Expected starts with {expected[:5]}, Got starts with {secret[:5] if secret else "None"}')
