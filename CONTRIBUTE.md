# Contribution Guide - TA-thehive-cortex

This file is an **index**. Each theme below lives in its own file under
`docs/themes/`; the line that follows each link says **when to open it**, so you
can decide without reading it.

> Conventions: commits follow
> [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## Themes

- [Build, packaging and safe deployment](docs/themes/build-packaging-deployment.md) —
  when you build the add-on, cut a release, run AppInspect, or deploy to a live
  Splunk instance.
- [The repository checks, and what each one exists to prevent](docs/themes/repository-checks.md) —
  when you add, change or silence a check under `tools/checks/`, or one of them
  fails.
- [Testing: what a guard actually proves](docs/themes/testing-and-coverage.md) —
  when you write or change a test, a mock, or a coverage floor.
- [Declarations that must resolve, and what a log line costs](docs/themes/declarations-and-logging.md) —
  when you touch a declaration split across two files, a log identifier, or a
  debug line.
- [The vendored libraries and their two path bootstraps](docs/themes/vendored-libraries.md) —
  when you touch `sys.path`, the vendored `thehive4py`/`cortex4py`, or a local
  patch.
- [The Splunk UI, its registries and its panels](docs/themes/splunk-ui-and-registries.md) —
  when you touch a dashboard, a panel, a generated registry, or an identifier
  carried as data.

## Where things live

| What | Where |
| :--- | :--- |
| Runtime third-party libraries | `package/bin/ta_thehive_cortex/libs/` |
| Why those libraries were patched | `tools/vendoring/LOCAL_PATCHES.md` |
| Repository checks | `tools/checks/` |
| UI definition (never edit the generated output) | `globalConfig.json` |
| Custom XML views | `package/default/data/ui/views/` |
| Runtime dependency pins | `package/lib/requirements.txt` |
