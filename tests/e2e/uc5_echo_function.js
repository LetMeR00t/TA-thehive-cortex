// TheHive Function `e2e-uc5-echo` -- the target of the end-to-end case UC5
// (tests/e2e/e2e_uc5_thehive_function.py). Type `api`, mode `Enabled`.
//
// Installed ONCE on the lab organisation by `python -m tests.e2e.uc5_function
// --install`, and left in place: it is the only global TheHive object the
// campaign keeps (user decision 2026-09-27). See tests/e2e/README.md.
//
// It turns what the add-on's `thehive_run_function` action pushes --
// {"events": [ {field: value, ...}, ... ]} -- into ONE alert, titled with the
// first event's `name`. The campaign sets `name` to its run prefix, so the
// alert is found by the test and removed by its teardown and by purge.py.
//
// ⚠️ The return value carries a `result` key on purpose: the add-on logs
// `THC-80 ERROR "Function didn't run correctly"` for any response without one
// (modalert_thehive_run_function_helper.py). TheHive's own documentation
// example returns the created alert as is, which the add-on would report as
// a failure although the Function ran.
function handle(input, context) {
    var events = (input && input.events) || [];
    var first = events.length > 0 ? events[0] : {};
    var title = first.name || "e2e-uc5-echo";
    var created = context.alert.create({
        type: "e2e-uc5-echo",
        source: "splunk-e2e",
        sourceRef: title,
        title: title,
        description: "Created by the TheHive Function e2e-uc5-echo from " +
            events.length + " event(s) pushed by the Splunk add-on " +
            "(end-to-end campaign, tests/e2e).",
        tags: ["e2e", "uc5"]
    });
    return { result: "alert created", alertId: created._id, events: events.length };
}
