# Build, packaging and safe deployment

> Trigger: read this when you build the add-on, cut a release, run AppInspect, or deploy to a live Splunk instance.

## Commits

Follow this convention: [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)

## Build & Packaging Lifecycle

### 1. Build (UCC Generation)
The Add-on uses the [Splunk UCC Generator](https://splunk.github.io/addonfactory-ucc-generator/). 

**Prerequisite:** You MUST use **Python 3.9** to run the UCC generator to ensure compatibility with Splunk's internal libraries.

To build the application, use the script -- it is the only supported way:

```bash
PYTHON=/path/to/python3.9 tools/build.sh 5.0.0
```

It runs `ucc-gen build` with the interpreter named explicitly, purges compiled
Python from `output/`, drops pip's `.exe` launchers, packages the archive, and
then runs `tools/checks/package_contents.sh` **on the archive**: a red check
fails the build. The CI build job runs the same script.

⚠️ Each of those steps used to be prose in this document. A Windows build of
5.0.0 that skipped them shipped **209 compiled Python files and 3 Windows
binaries** (#10): `ucc-gen` copies `package/bin` verbatim (so the `__pycache__`
of every local test run), pip compiles what it builds from source, and pip on
Windows installs Windows wheels. The script therefore forces
`charset_normalizer`'s pure-Python source distribution
(`--no-binary=charset_normalizer`) **on every platform**: pip on Linux ships
`.so` extensions just as pip on Windows ships `.pyd`, and one archive serves
every Splunk platform. The archive is pure Python whatever machine builds it,
and `package_contents.sh` refuses any native extension (`.so`, `.pyd`,
`.dll`, `.dylib`) and any `.exe` (decided 2026-09-27, #10).

### Who decides the version

**`ucc-gen` does, and it writes the answer back into your sources.**

- `--ta-version` is the source of truth. The build stamps it into `app.conf`,
  `app.manifest`, `VERSION` — **and into `globalConfig.json` itself**
  (`meta.version` is rewritten, then saved). Editing `meta.version` by hand
  before a build is redundant: the build overwrites it either way.
- **Omit `--ta-version` and the version comes from the latest git tag.** With no
  reachable tag it does NOT refuse: it builds `0.0.0+<sha>` (measured in CI,
  #16). Never ship that archive.
- `package/app.manifest` is **required** by `ucc-gen build` (without it:
  `FileNotFoundError`, #16). `.gitignore` excludes `*.manifest` (PyInstaller
  heritage), so it carries a narrow `!` exception for this one file — it was
  unversioned, and no clean clone could build, until 2026-09-27. Its version
  field is rewritten from `--ta-version` at build time.

### Tagging on red is a convention, not a lock

The Gitea CI (`.gitea/workflows/ci.yml`) runs on every push and on `v*` tags,
and turns red on a regression. **Nothing stops a `v*` tag from being pushed on a
red commit**: no tag protection is set (decision of 2026-09-27, #16). Check the
run of the exact commit is green before tagging.

Practical consequence: after a build, `git status` shows `globalConfig.json` as
modified even if you changed nothing. That is the generator writing into its own
input, not a stray edit.

### 2. Packaging

Done by `tools/build.sh` above. `ucc-gen package` names the archive
`TA-thehive-cortex/TA-thehive-cortex-<version>.tar.gz`; that file is what
Splunk receives and what every later step (AppInspect, deployment) must use --
never `output/`.

### 3. AppInspect (Splunk Cloud vetting)

Run the cloud checks on the `.spl` itself, never on `output/` -- the archive is
what Splunk receives.

```powershell
# Requires splunk-appinspect (Python 3.11; it does not install on 3.9).
splunk-appinspect inspect TA-thehive-cortex.spl --mode precert --included-tags cloud `
  --data-format json --output-file appinspect.json
```

Read the `summary` block of the JSON rather than the console log. Only
`failure` and `error` block a submission; `future_failure` announces a break in
a future Splunk release, and the `warning` entries here are informational
(frontend telemetry, deprecated SplunkJS, IPs inside vendored libraries).

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
- **Mako `appserver/templates/base.html` is emitted by `ucc-gen` itself**: AppInspect flags it (`future_failure` up to 4.3.0, a `warning` since 4.3.1; removed in Splunk 10.4) and advises "regenerate the app with UCC framework version 6.3.0 or later". That advice is not actionable -- UCC **6.6.0** still generates the file, and the source tree has no `package/appserver/templates/` at all. Nothing can be done from this repository; wait for an UCC release that stops emitting it. Do **not** delete the template by hand: it backs the configuration UI.
- **`requirements.txt` is a source file, not a virtualenv**: the standard Python `.gitignore` carries a bare `lib/` rule, which silently swallowed `package/lib/requirements.txt` -- the file pinning every runtime dependency of the add-on. A fresh clone could not rebuild the same TA. The `.gitignore` now re-includes it explicitly. When a build reads a file, check `git check-ignore -v` on that file before assuming it is versioned.
- **`python.required` is a version list, not an interpreter name**: `python.version = python3` (still required by current checks) and `python.required = 3.9, 3.13` are two different keys. Declaring `python.required` asserts compatibility with those interpreters, third-party libraries included -- set it deliberately, and mirror it in `globalConfig.json` under `meta.supportedPythonVersion`.
- **`ucc-gen` pins its own floor for `splunktaucclib`**: upgrading the generator can fail the build with "found but has the wrong version" long before any code changes. Bump the pin in `package/lib/requirements.txt` to match the generator's minimum.
- **Clean `.spl` (no compiled Python)**: `ucc-gen` installs pip deps with `--no-compile`, but it copies the source `bin/` verbatim. Running tests or scripts locally leaves `__pycache__`/`*.pyc` in `package/bin`, which then get embedded in `output/` and the `.spl`, failing Splunk Cloud AppInspect. Always strip `*.pyc`, `*.pyo` and `__pycache__` (in addition to `*.exe`/`*.pyd`) before `tar`-ing the package, and verify the archive itself with `tar -tzf TA-thehive-cortex.spl` rather than just checking `output/`.
