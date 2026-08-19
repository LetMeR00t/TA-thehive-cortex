# Release Notes - UNRELEASED

> ⚠️ This file accumulates what the **next** release must tell its users. It is
> renamed to `vX.Y.Z.md` when that version is tagged. Writing the upgrade note
> at the moment the fix is made is the only way it survives to the release: an
> upgrade instruction remembered at tagging time is an upgrade instruction lost.

## ⚠️ Manual step required after upgrading — sourcetypes of the add-on logs

### What was broken

Since **v4.0.0**, the search commands write their log as
`TA-thehive-cortex_<command>.log`, but `props.conf` still enumerated the
**v3.x** file names. The result: **23 of the add-on's 27 log files carried no
sourcetype at all**, and Splunk auto-learned one from the file name instead —
which is where `..-2`, `..-3` and `..-too_small` sourcetypes come from.

The symptom was misleading, and that is why it survived three minor versions:
the four `*_modalert` stanzas kept matching, so `props.conf` still looked
alive. Only the search commands were affected — plus, unnoticed until now, the
`thehive_create_a_new_alert` and `thehive_run_function` alert actions, which
never had a stanza of their own.

`props.conf` now matches the **shape** of the name rather than a list of
today's commands, so a command added tomorrow is covered on the day it ships.
The sourcetype `tathehivecortex:log` is also **defined** at last: until now it
was assigned everywhere and described nowhere, so line breaking and
timestamping fell back to Splunk's defaults on a format that begins with a
plain ISO date.

### 🖐️ What you must do — otherwise the fix will look like it did nothing

Once Splunk has **learned** a sourcetype it persists it into
`$SPLUNK_HOME/etc/apps/learned/local/props.conf`, as an **exact**
`[source::<full path>]` stanza. An exact-path stanza is *more specific* than
the wildcard stanza this add-on ships, so **it keeps winning** after the
upgrade.

1. Open `$SPLUNK_HOME/etc/apps/learned/local/props.conf`.
2. Remove every stanza whose source path points at a
   `TA-thehive-cortex_*.log` or a `*_modalert.log` file.
3. Restart Splunk.

Events indexed **before** the upgrade keep the sourcetype they were indexed
with — a sourcetype is decided at index time and is not rewritten
retroactively. To search across both, use the source rather than the
sourcetype:

```
index=_internal source=*TA-thehive-cortex_*.log
```

### Migration instructions of v4.0.0 are readable again

`release_notes/v4.0.0.md` disappeared in **v4.2.0**, while v4.2.0, v4.2.1 and
v4.2.2 all linked to it with a **relative** link — which resolves inside the
current tag, where the file no longer existed. Those instructions are labelled
*mandatory*, so the file is restored rather than the link rewritten: a relative
link to an absent file would break again at the next tag.
