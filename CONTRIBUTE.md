# Contribution Guide - TA-thehive-cortex

## Build & Packaging Lifecycle

### 1. Build (UCC Generation)
The Add-on uses the [Splunk UCC Generator](https://splunk.github.io/addonfactory-ucc-generator/). 

**Prerequisite:** You MUST use **Python 3.9** to run the UCC generator to ensure compatibility with Splunk's internal libraries.

To build the application:
```powershell
# Recommended build command
ucc-gen build --source TA-thehive-cortex/package --config TA-thehive-cortex/globalConfig.json --output output --ta-version 4.0.0 --overwrite -v --python-binary-name python
```
*Note: You may need to specify `--python-binary-name` (e.g., `python3.9` or the full path) if your default Python is not compatible.*

### 2. Packaging (.spl)
For the agent's environment, the following cleanup is applied to the `output/` folder before packaging:

```powershell
# Cleanup Windows binaries (keep Mako templates as they are required for UI)
Get-ChildItem "output/TA-thehive-cortex/lib" -Recurse -Include *.exe, *.pyd | Remove-Item -Force -ErrorAction SilentlyContinue;

# Create the .spl file
tar -cvzf TA-thehive-cortex.spl -C output TA-thehive-cortex
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
