from test_helper import TestContext
import json
import sys

def test_recovery():
    ctx = TestContext()
    spl = ctx.get_splunk_service()
    expected_api_key = ctx.get_thehive_api_key()
    
    print(f"Connecting to Splunk as {ctx.splunk_user}...")
    
    print("Listing storage passwords for TA-thehive-cortex...")
    _passwords = {}
    _was_json = {}
    
    for credential in spl.storage_passwords:
        realm = credential.realm
        if realm and "TA-thehive-cortex" in realm:
            username_ucc = credential.username
            if "``splunk_cred_sep``" in username_ucc:
                account_name = username_ucc.split("``splunk_cred_sep``")[0]
            else:
                account_name = username_ucc
                
            clear_password = credential.clear_password
            was_json = False
            
            try:
                cp_json = json.loads(clear_password)
                if isinstance(cp_json, dict):
                    val = cp_json.get("password", clear_password)
                    if val != clear_password:
                        was_json = True
                else:
                    val = clear_password
            except Exception:
                val = clear_password

            if val != "******" and val != "********":
                if "``splunk_cred_sep``" in val:
                    continue

                current_was_json = _was_json.get(account_name, False)
                current_val = _passwords.get(account_name, "")

                if (account_name not in _passwords) or \
                   (was_json and not current_was_json) or \
                   (was_json == current_was_json and len(val) > len(current_val)):
                    
                    _passwords[account_name] = val
                    _was_json[account_name] = was_json

    if 'local' in _passwords:
        secret = _passwords['local']
        print(f"Found secret for 'local' (length {len(secret)})")
        if secret == expected_api_key:
            print("SUCCESS: Correct API Key recovered!")
        else:
            print(f"FAILURE: Got {secret[:5]}..., expected {expected_api_key[:5]}...")
    else:
        print("FAILURE: 'local' account not found!")

if __name__ == "__main__":
    test_recovery()
