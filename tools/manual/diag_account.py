"""Read the TheHive API key the add-on resolves for an instance, and compare it
to the expected one.

Never prints any part of either key: only whether they match and their lengths.

    python tools/manual/diag_account.py [instance_name]   # default: "Org L2"
"""
import sys

from diag_helper import TestContext

# Initialize test context (sets sys.path to the installed app)
ctx = TestContext()

import globals  # noqa: E402
from common import LoggerFile, Settings  # noqa: E402
from ta_logging import setup_logging  # noqa: E402

instance = sys.argv[1] if len(sys.argv) > 1 else "Org L2"

globals.initialize_globals()
logger_file = LoggerFile(setup_logging("script"), "TEST")
configuration = Settings(ctx.get_splunk_service(), None, logger_file)

print(f"Accounts found: {list(configuration.getAccounts().keys())}")
user, secret = configuration.getInstanceUsernameApiKey(instance)
expected = ctx.get_thehive_api_key()
print(f"{instance} -> User: {user}")
if secret == expected:
    print("API Key is CORRECT")
else:
    print(f"API Key is INCORRECT (got length {len(secret) if secret else 0}, "
          f"expected length {len(expected)})")
