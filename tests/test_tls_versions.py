import requests
import ssl
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from test_helper import TestContext

def test_version(protocol, name, ctx):
    class TLSAdapter(HTTPAdapter):
        def init_poolmanager(self, connections, maxsize, block=False):
            self.poolmanager = PoolManager(
                num_pools=connections,
                maxsize=maxsize,
                block=block,
                ssl_version=protocol
            )
    try:
        s = requests.Session()
        s.mount('https://', TLSAdapter())
        ca_path = ctx.get_ca_path()
        api_key = ctx.get_thehive_api_key()
        url = f"{ctx.get_thehive_url()}/api/v1/user/current"
        
        r = s.get(url, 
                  headers={'Authorization': f'Bearer {api_key}'}, 
                  verify=ca_path, timeout=5)
        print(f'{name}: Success (Status {r.status_code})')
    except Exception as e:
        print(f'{name}: Failed - {e}')

if __name__ == "__main__":
    context = TestContext()
    print('Testing various TLS versions...')
    test_version(ssl.PROTOCOL_TLSv1_1, 'TLS 1.1', context)
    test_version(ssl.PROTOCOL_TLSv1_2, 'TLS 1.2', context)
    try:
        test_version(ssl.PROTOCOL_TLS, 'TLS (Auto/1.3)', context)
    except Exception: pass
