# Manual diagnostic scripts

These are **not tests**. They are throwaway scripts written while chasing a
specific problem against a real Splunk or a real TheHive: they print what they
find and they exit.

They used to live in `tests/`, named `test_*.py`. That was a problem, and not a
cosmetic one:

- **none of them contains a single assertion** — `print('API Key is CORRECT')`
  is not a verification, and a script that cannot go red proves nothing;
- they were picked up by `unittest discover`, and `test_helper.py` called
  `sys.exit(1)` when an environment variable was missing, so **the whole run
  died** instead of skipping. Fourteen errors that hid whatever a real
  regression might have been saying.

They are kept because they still carry knowledge — how to reach a Splunk REST
endpoint, how the UCC credential format is laid out, how a TLS handshake fails
against a custom CA. That knowledge is the raw material for the end-to-end
suite, which will do properly what these scripts sketch: create configuration
on the fly, exercise it, verify both sides, then delete everything.

## Running one

They need a real environment. `diag_helper.py` expects `SPLUNK_USER`,
`SPLUNK_PASSWORD`, `THEHIVE_URL` and `THEHIVE_API_KEY`, and it still exits
rather than skipping — acceptable now that it can no longer take a test run
down with it.

```bash
python tools/manual/diag_conn.py
```

⚠️ Never put those credentials in the repository, in a command line that ends
up in shell history, or in a CI secret of this **public** repository.

## What each one answers

| Script | Question |
| :--- | :--- |
| `diag_account.py [instance]` | Does the add-on resolve the expected API key for an instance? Prints match and lengths, **never a character of a key**. |
| `diag_conn.py [--insecure]` | Does plain `requests` reach TheHive with the app's CA file? `--insecure` tells a CA problem from a network one. |
| `diag_tls.py` | Which TLS protocol version does the server accept? |
| `diag_thehive4py.py` | Does the vendored `thehive4py` client reach TheHive? |
| `diag_rest_direct.py` | Which credential entries does Splunk's `storage/passwords` hold (realm and user only)? |

The `_fixed` / `_final` variants that accumulated while chasing one problem were
merged into these (#42). Two of them printed the full API key: a diagnostic
prints whether a secret matches, never the secret.
