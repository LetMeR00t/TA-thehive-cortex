# Contribution Guide - TA-thehive-cortex

## Commits

Follow this convention: [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)

## Build & Packaging Lifecycle

### 1. Build (UCC Generation)
The Add-on uses the [Splunk UCC Generator](https://splunk.github.io/addonfactory-ucc-generator/). 

**Prerequisite:** You MUST use **Python 3.9** to run the UCC generator to ensure compatibility with Splunk's internal libraries.

To build the application:
```powershell
# Recommended build command
ucc-gen build --source TA-thehive-cortex/package --config TA-thehive-cortex/globalConfig.json --output output --ta-version 4.2.0 --overwrite -v --python-binary-name python
```
*Note: You may need to specify `--python-binary-name` (e.g., `python3.9` or the full path) if your default Python is not compatible.*

### 2. Packaging (.spl)
For the agent's environment, the following cleanup is applied to the `output/` folder before packaging:

```powershell
# Cleanup compiled-Python artifacts. ucc-gen copies the source bin/ as-is, so any
# stale __pycache__/*.pyc left in package/bin (e.g. from running tests locally)
# would ship inside the .spl and fail Splunk Cloud AppInspect.
Get-ChildItem "output/TA-thehive-cortex" -Recurse -Include *.pyc, *.pyo -File | Remove-Item -Force -ErrorAction SilentlyContinue;
Get-ChildItem "output/TA-thehive-cortex" -Recurse -Directory | Where-Object { $_.Name -eq "__pycache__" } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue;

# Cleanup Windows binaries (keep Mako templates as they are required for UI)
Get-ChildItem "output/TA-thehive-cortex/lib" -Recurse -Include *.exe, *.pyd -File | Remove-Item -Force -ErrorAction SilentlyContinue;

# Create the .spl file
tar -czf TA-thehive-cortex.spl -C output TA-thehive-cortex
```

---

## Autonomous Safe Deployment (CRITICAL)
**NEVER** delete the `local/` folder in the Splunk directory during a deployment. 

Deployment must be performed directly via shell commands (PowerShell) by strictly following these steps:
1. Stop Splunk to release file locks.
2. Temporarily move the existing `local/` folder to a backup directory outside the app's tree.
3. Remove the old version of the application.
4. Deploy the new build from `output/`.
5. Restore the backed-up `local/` folder.
6. Restart Splunk.

**Direct command example:**
```powershell
& "C:\Program Files\Splunk\bin\splunk.exe" stop; if (Test-Path "C:\Program Files\Splunk\etc\apps\TA-thehive-cortex\local") { Move-Item "C:\Program Files\Splunk\etc\apps\TA-thehive-cortex\local" "$env:TEMP\TA_local_backup" -Force }; Remove-Item "C:\Program Files\Splunk\etc\apps\TA-thehive-cortex" -Recurse -Force -ErrorAction SilentlyContinue; Copy-Item -Path "output\TA-thehive-cortex" -Destination "C:\Program Files\Splunk\etc\apps\" -Recurse -Force; if (Test-Path "$env:TEMP\TA_local_backup") { if (-not (Test-Path "C:\Program Files\Splunk\etc\apps\TA-thehive-cortex\local")) { New-Item -Path "C:\Program Files\Splunk\etc\apps\TA-thehive-cortex\local" -ItemType Directory }; Copy-Item -Path "$env:TEMP\TA_local_backup\*" -Destination "C:\Program Files\Splunk\etc\apps\TA-thehive-cortex\local" -Recurse -Force; Remove-Item "$env:TEMP\TA_local_backup" -Recurse -Force }; & "C:\Program Files\Splunk\bin\splunk.exe" start
```

---

## Lessons Learned & Best Practices

*This section is for sharing generic technical lessons learned during development. Do not include setup-specific or sensitive information.*

- **Python Compatibility**: Always use Splunk's internal Python version (3.9+) for builds and local testing to ensure library compatibility.
- **UCC Framework**: All UI changes MUST be made in `globalConfig.json`. Manual changes to `default/data/ui` will be overwritten during the next build. Note: custom XML views are stored in `package/default/data/ui/views`.
- **Splunk Tokens Evaluation**: When checking if a dashboard token is defined in an SPL `eval`, always escape the comparison token with `$$` (e.g., `"$token$" == "$$token$$"`). This prevents the condition from becoming always true after token substitution (e.g., `"-1d" == "-1d"`).
- **Library Isolation**: Third-party libraries must be placed in `package/bin/ta_thehive_cortex/libs` to avoid conflicts with other Splunk apps.
- **Clean `.spl` (no compiled Python)**: `ucc-gen` installs pip deps with `--no-compile`, but it copies the source `bin/` verbatim. Running tests or scripts locally leaves `__pycache__`/`*.pyc` in `package/bin`, which then get embedded in `output/` and the `.spl`, failing Splunk Cloud AppInspect. Always strip `*.pyc`, `*.pyo` and `__pycache__` (in addition to `*.exe`/`*.pyd`) before `tar`-ing the package, and verify the archive itself with `tar -tzf TA-thehive-cortex.spl` rather than just checking `output/`.
