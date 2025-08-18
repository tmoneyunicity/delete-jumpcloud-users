⸻

JumpCloud Suspended User Cleanup

Overview

This repository contains two Python scripts for automating the cleanup of suspended users in JumpCloud.
The scripts identify users who are suspended and not in the “DO NOT DELETE” (DND) group, then either list them (safe test mode) or delete them via the JumpCloud API.
	•	list-users-to-delete.py – Safe, read-only. Lists candidates and posts to Slack.
	•	delete-users.py – Production cleanup. Unbinds users from devices. Deletes candidates and posts results to Slack.

⸻

Features
	•	Automatically fetches all JumpCloud users and members of the DND group.
	•	Excludes all members of the DND group from deletion.
	•	Slack notifications for transparency.
	•	Debug logging option for troubleshooting.
	•	Designed for hands-off execution in GitHub Actions.

⸻

Requirements
	•	Python 3.11+
	•	requests library (pip install -r requirements.txt)
	•	JumpCloud admin API key with permission to:
	•	List system users
	•	List group members
	•	Delete system users (delete script only)
	•	Slack Incoming Webhook (optional but recommended)

⸻

Setup

1. Clone Repo

git clone https://github.com/<your-org>/<repo-name>.git
cd <repo-name>

2. Install Requirements

pip install -r requirements.txt

3. Add GitHub Actions Secrets

In GitHub → Settings → Secrets and variables → Actions add:

Secret Name	Description
JUMPCLOUD_API_KEY	JumpCloud API key
DND_GROUP_ID	JumpCloud group ID for the “DO NOT DELETE” group
SLACK_WEBHOOK_URL	Slack Incoming Webhook URL
DEBUG (optional)	true for verbose logging
INACTIVITY_THRESHOLD (optional)	Kept for compatibility; unused in current logic


⸻

Running Locally

List Mode (safe):

python list-users-to-delete.py

Delete Mode (production):

python delete-users.py


⸻

GitHub Actions Automation

The scripts can be run manually or on a schedule.

Example .github/workflows/cleanup.yml:

name: JumpCloud Suspended User Cleanup

on:
  workflow_dispatch: # Manual trigger
  schedule:
    - cron: "0 14 1-7 * 1" # First Monday of every month, 14:00 UTC (~7 AM PT)

jobs:
  cleanup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run cleanup script
        run: python list-users-to-delete.py
        env:
          JUMPCLOUD_API_KEY: ${{ secrets.JUMPCLOUD_API_KEY }}
          DND_GROUP_ID: ${{ secrets.DND_GROUP_ID }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
          DEBUG: ${{ secrets.DEBUG || 'false' }}


⸻

Slack Output Example

List Script:

*JumpCloud Suspended User Review:*
The following users are suspended and NOT in `DO NOT DELETE` group:
- user1@example.com
- user2@example.com

Delete Script:

*JumpCloud User Deletion Report:*
The following suspended users (NOT in `DO NOT DELETE`) were unbound from all devices and were deleted:
- user1@example.com ✅
- user2@example.com ✅


⸻

Safety Notes
	•	Always run the list script first to verify candidates before enabling deletion.
	•	Deleted JumpCloud users cannot be restored—coordinate with HR and IT before enabling automatic deletion.
	•	Keep at least one test account in the DND group to verify exclusion logic.

⸻

License

This repository is for internal use within Unicity International and is not licensed for public redistribution.

⸻
