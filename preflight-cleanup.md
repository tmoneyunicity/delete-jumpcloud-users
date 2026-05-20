# Preflight Cleanup — May 2026

This document records all changes made before the first production run of `delete_users.py`. The list script (`list-users-to-delete.py`) was validated as a POC but the delete script and its workflow were never executed. The issues below were identified during a full review prior to enabling deletion.

---

## Critical Fixes (would have caused immediate failure)

### 1. `delete-jumpcloud-users.yml` — wrong secret names
**Before:** `JC_API_KEY` and `SLACK_WEBHOOK`
**After:** `JUMPCLOUD_API_KEY` and `SLACK_WEBHOOK_URL`

The script reads `os.environ["JUMPCLOUD_API_KEY"]` and `os.environ["SLACK_WEBHOOK_URL"]`. The workflow was passing different names, so every run would have crashed with a `KeyError` before doing anything.

---

### 2. `delete-jumpcloud-users.yml` — missing Python setup and pip install
The workflow jumped straight to `python delete_users.py` with no `Set up Python` or `Install dependencies` steps. The `requests` library would not be present on the runner.

**Added:**
```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.11'

- name: Install dependencies
  run: pip install -r requirements.txt
```

---

### 3. `delete-jumpcloud-users.yml` — missing `DND_GROUP_ID` env var
The script requires `DND_GROUP_ID` but the workflow `env:` block did not include it. Added alongside the other three secrets.

---

### 4. `delete-jumpcloud-users.yml` — "first Monday" shell guard did not work
**Before:**
```bash
exit 0  # marks step as success; subsequent steps still run
```
In GitHub Actions, `exit 0` passes the step — it does not skip downstream steps. On a non-Monday manual dispatch the checkout and deletion would have run anyway.

**After:** Removed the shell guard entirely. The cron expression `0 14 1-7 * 1` already restricts scheduled runs to the first Monday. `workflow_dispatch` runs unconditionally (intentional — useful for forced manual runs). This is documented in the README.

---

## API Endpoint Fixes (`delete_users.py`)

### 5. Wrong endpoint for listing user-bound systems
**Before:** `GET /api/v2/systemusers/{user_id}/computers`
**After:** `GET /api/v2/systemusers/{user_id}/systems`

The `/computers` path does not exist in the JumpCloud v2 API and would have returned 404s for every user, silently skipping all unbind operations.

---

### 6. Wrong method for unbinding a user from a system
**Before:** `DELETE /api/v2/systemusers/{user_id}/computers/{device_id}`
**After:** `POST /api/v2/systemusers/{user_id}/associations` with body `{"op": "remove", "type": "system", "id": "<system_id>"}`

JumpCloud v2 manages user-system associations through the graph associations API, not a DELETE on a sub-resource path. The old approach would have returned 404s and (because there was no `raise_for_status()`) proceeded silently to delete users without unbinding them.

---

## Logic Fixes

### 7. Removed 90-day `lastLogin` filter from `delete_users.py`
The original delete script filtered out suspended users who had no `lastLogin` or had logged in within 90 days. The list script had no such filter. This meant users shown in the Slack "review" output would not necessarily be deleted — with no explanation.

Both scripts now use identical criteria: **suspended = true AND not in DND group**. The list output now exactly reflects what the delete script will act on.

Also removed the associated dead code: `from datetime import datetime, timedelta`, `cutoff_date`, and `last_login` variable.

---

## Security / Robustness Fixes

### 8. Added `validate_env()` to both scripts
**Before:** `os.environ["KEY"]` raises a raw `KeyError` if a secret is not set, with no indication of which variable is missing.
**After:** Both scripts call `validate_env()` at startup, which checks all required variables and raises a clear `EnvironmentError` listing the missing names.

---

### 9. Added `raise_for_status()` to `delete_user()` in `delete_users.py`
A failed deletion would previously be silently ignored. The function now raises on non-2xx responses so failures surface immediately.

---

### 10. Added null guard for `SLACK_WEBHOOK_URL` in `delete_users.py`
The list script already had `if not SLACK_WEBHOOK_URL: return` in `send_slack_message()`. The delete script did not, and would crash with a `MissingSchema` error if the secret was absent. Now consistent across both scripts.

---

## Cleanup

### 11. Removed `python-dateutil` from `requirements.txt`
Never imported by either script. Only `requests` is needed.

### 12. Removed unused `import json` from `list-users-to-delete.py`
The `send_slack_message()` function was using `data=json.dumps(payload)`. Changed to `json=payload` (letting `requests` handle serialization), matching `delete_users.py`. The `json` import is no longer needed.

### 13. Wired up `DEBUG` variable in both scripts
`DEBUG` was parsed from the environment in `list-users-to-delete.py` but never used. Both scripts now have a `debug()` helper that gates on the `DEBUG` flag. Debug output logs user/DND fetch counts and candidate totals. The `DEBUG` secret is documented in the README.

### 14. Fixed double `resp.json()` call in `list-users-to-delete.py`'s `get_dnd_group_user_ids()`
The loop iterated `resp.json()` and then called `len(resp.json())` again for the pagination check — parsing the response body twice per page. Fixed by caching the result in `data` first.

### 15. Removed `INACTIVITY_THRESHOLD` from `test-list.yml`
This env var was passed to the list script but never read. Removed to avoid confusion.

### 16. Updated `actions/setup-python` from `@v4` to `@v5` in both workflows

### 17. Fixed `communication_template.md` schedule description
"first day of each month" → "first Monday of each month"

### 18. Updated README
- Removed `INACTIVITY_THRESHOLD` from the secrets table
- Updated the workflow example to match the actual `delete-jumpcloud-users.yml`
- Updated the delete script Slack output example to match actual output format
- Added note that `workflow_dispatch` runs unconditionally
- Added Safety Note clarifying both scripts now use identical candidate criteria

---

## Recommended Before First Run

1. Confirm you have a valid `JUMPCLOUD_API_KEY` set in GitHub Secrets under the name `JUMPCLOUD_API_KEY`.
2. Run the list workflow (`test-list.yml`) and verify the Slack output looks correct.
3. Confirm at least one account is in the DND group and does **not** appear in the list output.
4. Trigger `delete-jumpcloud-users.yml` manually via `workflow_dispatch` for the first run so you can monitor the output before enabling the schedule.
