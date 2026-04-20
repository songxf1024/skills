name: scut-review-monitor
description: Check or monitor the SCUT thesis blind-review status page through the graduate portal, refresh cookies through a local Python helper, and use the helper for login plus status query when the user asks to check blind-review status.
metadata: {"openclaw":{"emoji":"🎓","skillKey":"scut-review-monitor","requires":{"bins":["python3"]},"homepage":"https://clawhub.ai/songxf1024/scut-review-monitor"}}
user-invocable: true
--------------------

# scut-review-monitor

Use the local helper script at `{baseDir}/portal_monitor.py`.
The local config file is `{baseDir}/config.json`.

## When to invoke this skill

Invoke this skill whenever the user is asking about the SCUT blind-review page, blind-review progress, blind-review result, or needs portal re-login for this page.

Typical trigger utterances include:

* `帮我查一下盲审状态`
* `查一下论文盲审状态`
* `看下现在盲审到哪一步了`
* `帮我登录研究生系统查盲审`
* `盲审状态有变化吗`
* `帮我持续盯一下盲审状态`

If the user is asking to **check** blind-review status, this skill should be selected directly.
Do not ask the user which script or command to run.
Choose the helper subcommand according to the workflow below.

## Execution policy

### Default flow for “帮我查一下盲审状态”

For requests like `帮我查一下盲审状态`, follow this order:

1. Run a one-time query first:

```bash
python3 "{baseDir}/portal_monitor.py" check-once
```

2. If the helper reports that login is required, cookies are missing, or the portal session is invalid, immediately switch to login flow:

```bash
python3 "{baseDir}/portal_monitor.py" login
```

3. During login, parse the helper output and surface the useful result, especially the QR-code image URL if image hosting is enabled.

4. After login succeeds and cookies are saved, run the one-time query again:

```bash
python3 "{baseDir}/portal_monitor.py" check-once
```

5. Return the final blind-review status.

Treat `login` as part of the query workflow when needed, not as a separate user task.

### Continuous monitoring flow

Only run foreground monitoring when the user explicitly asks for continuous watching, auto-refresh checking, or change notification.

```bash
python3 "{baseDir}/portal_monitor.py" monitor
```

Do not silently start long-running monitoring for a simple one-time query.

## What this skill is good for

* One-time checks of the current thesis blind-review status text.
* Login bootstrap through the graduate portal and local cookie refresh.
* Headless QR-code extraction during login for remote scanning.
* Optional upload of QR-code images to the configured image-hosting API so channels that cannot send images directly can still show the QR code through a URL.
* Foreground monitoring of blind-review status changes.

## Important constraints

* This is a local skill and requires `python3` on the host machine.
* The helper is intended to run in headless mode for remote or server-side execution.
* Do not expose notification secrets or config secrets.
* Do not start long-lived background jobs unless the user explicitly asked for monitoring.
* If the user asks for daemonized or scheduled monitoring, explain that it should be supervised outside the skill by systemd, launchd, cron, or another scheduler.

## Configuration

This skill reads runtime settings from `{baseDir}/config.json`.
If the file does not exist yet, copy `{baseDir}/config.json.example` to `{baseDir}/config.json` and fill in the required fields.

Commonly edited fields include:

* `watch_xpath`
* `monitor_interval_seconds`
* `notify.notify_url`
* `notify.notify_target`
* `notify.notify_key`
* `notify.serverchan_sendkey`
* `image_upload.enabled`
* `image_upload.output_format`
* `image_upload.cdn_domain`

## Helper commands

### Login and save cookies

```bash
python3 "{baseDir}/portal_monitor.py" login
```

Use this when the portal session is invalid or when `check-once` indicates that login is required.

During login, if the page exposes a QQ login QR code under `#qrcodeQQLogin`, the helper should export the QR code locally. If image hosting is enabled, the helper should also upload that QR code and produce a public URL.

If the page shows `二维码已失效`, the helper should refresh the page and continue exporting the new QR code.

### One-time query

```bash
python3 "{baseDir}/portal_monitor.py" check-once
```

Use this for ordinary user requests such as `帮我查一下盲审状态`.
This is the default entry point for query-like requests.

### Foreground monitoring

```bash
python3 "{baseDir}/portal_monitor.py" monitor
```

Use this only when the user explicitly asks for continuous monitoring.

## Response guidance

* For ordinary query requests, prefer `check-once` first.
* If login is required, run `login` and continue the workflow automatically.
* If login produces a QR-code URL, return a concise instruction telling the user to open that URL and scan it.
* After login succeeds, run `check-once` again and return the actual blind-review status, not just “登录成功”.
* If the watched XPath no longer matches, explain that the portal page structure likely changed.
* If the user asks to modify the watched field, update `{baseDir}/config.json` or the helper script rather than guessing values in the reply.
* For monitoring changes, summarize the previous value and the new value.

## Output handling

The helper emits structured stdout for integration.
Parse the helper output and use the final result as the source of truth.

Guidelines:

* Treat the last `SKILL_RESULT ...` line as the authoritative result.
* `SKILL_EVENT ...` lines are intermediate progress events.
* Prefer structured fields such as `status`, `needs_login`, `qrcode_url`, and `watched_text`.
* Do not rely on free-form text matching when a structured field is present.
* `qrcode_data_file` should not be used in structured handling.

For QR-code login scenarios, prioritize:

* whether login is required
* the uploaded QR-code URL when available
* the follow-up blind-review status after login completes
