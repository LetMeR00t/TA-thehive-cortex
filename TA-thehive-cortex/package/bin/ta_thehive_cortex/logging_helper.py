import ta_thehive_cortex_declare

# Third-party imports
from solnlib.log import Logs


def get_logger(name):
    return Logs().get_logger(name)
