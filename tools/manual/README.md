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
