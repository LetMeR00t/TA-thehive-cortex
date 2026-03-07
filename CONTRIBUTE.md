# Contribution Guidelines

## Commit Messages
All commit messages must follow the [Conventional Commits (v1.0.0)](https://www.conventionalcommits.org/en/v1.0.0/) specification.

Structure:
`<type>[optional scope]: <description>`

Example:
`feat(ui): update instances tab title to be more descriptive`

## Local Deployment Guidelines
When deploying the application locally to Splunk (`etc/apps/TA-thehive-cortex`), **ALWAYS** follow this workflow to ensure compliance and preserve configuration:

1. **Build**: Run `ucc-gen build` to generate the latest version of the app.
2. **Inspect**: Run `splunk-appinspect inspect output/TA-thehive-cortex --included-tags cloud` to ensure no errors are introduced for Splunkbase/Cloud compliance.
3. **Backup**: Backup the existing `local/` folder from the Splunk app directory if it exists.
4. **Deploy**: 
    - Remove the old app folder from `etc/apps/`.
    - Copy the new app version from `output/`.
    - Restore the `local/` folder into the new app directory.
5. **Refresh**: Perform a `/debug/refresh` in Splunk or restart the service if necessary.


