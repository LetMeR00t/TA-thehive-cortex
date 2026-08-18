import sys
import os
from test_helper import TestContext

# Initialize test context
ctx = TestContext()

from common import Settings, LoggerFile
from ta_logging import setup_logging
import globals

globals.initialize_globals()
logger = setup_logging('script')
logger_file = LoggerFile(logger, 'TEST')

# Connect to Splunk
spl = ctx.get_splunk_service()

configuration = Settings(spl, None, logger_file)
user, secret = configuration.getInstanceUsernameApiKey('Org L2')
print(f'Org L2 -> User: {user}')
print(f'Got Secret: {secret}')
