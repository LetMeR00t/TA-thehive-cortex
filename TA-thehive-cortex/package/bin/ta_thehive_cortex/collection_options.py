# encoding = utf-8
"""What the alerts & cases collection keeps, per object type, of what the form offers.

The input form (`globalConfig.json`, services `thehive_alerts_cases` and
`backfill_alerts_cases`) offers one flat list of "additional information" and
"extra data" options, grouped as "Common", "Alerts only" and "Cases only". At
run time each object type only keeps the options it can serve; this module is
the single place that decides which ones.

⚠️ An option the form offers for a type and that is missing here is accepted,
saved in the input's configuration, and then dropped without a word at every
run (#37: `ttps` for alerts). `tools/checks/collection_options_honoured.py`
compares this module with the form so that gap cannot reopen silently.
"""

ADDITIONAL_INFORMATION = {
    "alerts": ("observables", "attachments", "ttps"),
    "cases": ("tasks", "observables", "attachments", "pages", "ttps"),
}

EXTRA_DATA = {
    "alerts": ("caseNumber", "status"),
    "cases": ("status", "alerts"),
}


def options_for(input_type, additional_information, extra_data):
    """Return the (additional_information, extra_data) lists kept for `input_type`.

    The order the user selected is preserved; unknown types keep nothing.
    """
    kept_information = ADDITIONAL_INFORMATION.get(input_type, ())
    kept_extra = EXTRA_DATA.get(input_type, ())
    return (
        [item for item in additional_information if item in kept_information],
        [item for item in extra_data if item in kept_extra],
    )
