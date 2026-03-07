# encode = utf-8

import os
import sys
import re

ta_name = 'TA-thehive-cortex'
pattern = re.compile(r"[\\/]etc[\\/]apps[\\/][^\\/]+[\\/]bin[\\/]?$")
new_paths = [path for path in sys.path if not pattern.search(path) or ta_name in path]

# UCC framework standard lib directory
new_paths.insert(0, os.path.sep.join([os.path.dirname(os.path.dirname(__file__)), "lib"]))
# Custom logic directory
new_paths.insert(0, os.path.sep.join([os.path.dirname(__file__), "ta_thehive_cortex"]))

sys.path = new_paths
