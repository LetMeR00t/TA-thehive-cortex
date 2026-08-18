import requests
import ssl
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from test_helper import TestContext

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_version=ssl.PROTOCOL_TLSv1_2
        )

def run_test():
    ctx = TestContext()
    s = requests.Session()
    s.mount('https://', TLSAdapter())
    
    ca_path = ctx.get_ca_path()
    api_key = ctx.get_thehive_api_key()
    url = f"{ctx.get_thehive_url()}/api/v1/user/current"
    
    try:
        r = s.get(
            url, 
            headers={'Authorization': f'Bearer {api_key}'}, 
            verify=ca_path,
            timeout=10
        )
        print(f'Status: {r.status_code}')
        print(f'Body: {r.text[:100]}')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    run_test()
