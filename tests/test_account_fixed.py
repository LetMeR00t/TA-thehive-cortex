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
user, secret = configuration.getInstanceUsernameApiKey('Org L2')
print(f'Org L2 -> User: {user}')
expected = ctx.get_thehive_api_key()
if secret == expected:
    print('API Key is CORRECT')
else:
    print(f'API Key is INCORRECT.')
    print(f'Expected: {expected}')
    print(f'Got:      {secret}')
