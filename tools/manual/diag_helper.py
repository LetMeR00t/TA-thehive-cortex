import os
import sys

class TestContext:
    def __init__(self):
        self.app_root = r'C:\Program Files\Splunk\etc\apps\TA-thehive-cortex'
        self._setup_path()
        
        # Force presence of environment variables
        try:
            self.splunk_user = os.environ["SPLUNK_USER"]
            self.splunk_password = os.environ["SPLUNK_PASSWORD"]
            self.thehive_api_key = os.environ["THEHIVE_API_KEY"]
            # No default: a fallback URL would be one contributor's own host.
            self.thehive_url = os.environ["THEHIVE_URL"]
        except KeyError as e:
            print(f"ERROR: Missing environment variable {e}")
            sys.exit(1)
        
        self._splunk_service = None

    def _setup_path(self):
        paths = [
            os.path.join(self.app_root, 'bin'),
            os.path.join(self.app_root, 'lib'),
            os.path.join(self.app_root, 'bin', 'ta_thehive_cortex', 'libs')
        ]
        for p in paths:
            if p not in sys.path:
                sys.path.insert(0, p)

    def get_splunk_service(self, host='localhost', port=8089):
        import splunklib.client as client
        if not self._splunk_service:
            try:
                self._splunk_service = client.connect(
                    host=host, 
                    port=port, 
                    username=self.splunk_user, 
                    password=self.splunk_password
                )
                # Export session key for solnlib support in common.py
                os.environ["SPLUNK_SESSION_KEY"] = self._splunk_service.token
            except Exception as e:
                print(f"ERROR: Could not connect to Splunk: {e}")
                sys.exit(1)
        return self._splunk_service

    def get_thehive_api_key(self):
        return self.thehive_api_key

    def get_thehive_url(self):
        return self.thehive_url

    def get_ca_path(self):
        return os.path.join(self.app_root, 'local', 'cacert.crt')
