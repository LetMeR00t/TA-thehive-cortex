# Contribution Guide - TA-thehive-cortex

## Build & Packaging Lifecycle

### 1. Build (UCC Generation)
The Add-on uses the [Splunk UCC Generator](https://splunk.github.io/addonfactory-ucc-generator/). To build the application, ensure you have Python 3.9 installed and run the following command from the project root:

```powershell
# Recommended build command
ucc-gen build --source TA-thehive-cortex/package --config TA-thehive-cortex/globalConfig.json --output output --ta-version 4.0.0 --overwrite -v --python-binary-name python
```
*Note: You may need to specify `--python-binary-name` (e.g., `python3.9` or the full path) if your default Python is not compatible.*

### 2. Package generation (.spl)
Once the UCC build is completed in the `output/` folder, the `.spl` file (tar.gz archive compatible with Splunkbase/Cloud) must be generated. It is critical to perform a cleanup to ensure AppInspect compliance.

**Packaging procedure:**
1. Navigate to the `output/` folder.
2. Purge residual files (Windows binaries, Mako templates, cache).
3. Compress the app folder in `.tar.gz` format and rename it to `.spl`.

**Recommended PowerShell command (for Windows users):**
```powershell
# Final cleanup before compression
Get-ChildItem "output/TA-thehive-cortex/lib" -Recurse -Include *.exe, *.pyd | Remove-Item -Force -ErrorAction SilentlyContinue;

# Creating the .spl file (tar.gz)
tar -cvzf TA-thehive-cortex.spl -C output TA-thehive-cortex
```

## UCC Architecture
The add-on uses the UCC framework. The `globalConfig.json` file is the source of truth for the user interface and modular inputs.

## Lessons Learned (v4.0.0 Migration)

### 1. Modular Inputs Management
- **Business Logic**: All collection logic must reside in `package/bin/input_module_<name>.py`.
- **Wrappers**: Never manually create wrapper scripts (`thehive_alerts_cases.py`, etc.) in `package/bin/`. UCC generates them automatically in `output/`. If they exist in the source, they can cause conflicts or unexpected behaviors.
- **Parameters**: Ensure all parameters defined in `globalConfig.json` (e.g., `max_size_value`, `fields_removal`) are retrieved via `helper.get_arg('<name>')` in the Python script.

### 2. Cleanup and Redundancy
- **Binary Folders**: Avoid uppercase folders like `TA-thehive-cortex/` inside `bin/`. Prefer a lowercase Python package (e.g., `ta_thehive_cortex/`) and configure `sys.path` in a declaration file (e.g., `ta_thehive_cortex_declare.py`).
- **Useless Scripts**: Systematically remove old scripts from v3.9.0 that do not follow the `input_module_*.py` pattern.

### 3. Splunk AppInspect & Quality
- **DATETIME_CONFIG**: In `props.conf`, never leave `DATETIME_CONFIG` empty. If Splunk should handle time automatically, it is better to remove the line rather than leaving it empty, to avoid AppInspect failure.
- **Navigation (XML)**: UCC generates its own `default.xml`. If you restore a manual file, ensure it contains the necessary entries for UCC pages (`configuration`, `inputs`, `dashboard`).
- **Verbose Build**: Always use `ucc-gen build ... -v` to identify conflicting files during generation.

### 4. Deployment (Windows)
- If `.pyd` or `.exe` files are locked, it is necessary to completely stop Splunk AND kill orphan Python processes before attempting a folder copy.

### 5. Preservation of Local Configuration
- **local/ folder**: During deployment (copying `output/` to Splunk), it is imperative to preserve the existing `local/` folder in Splunk. This folder contains encrypted passwords, accounts, and instance configurations defined by the user via the interface.
- **Strategy**: Always backup or temporarily move the `local/` folder before deleting the old app version to install the new UCC build.
