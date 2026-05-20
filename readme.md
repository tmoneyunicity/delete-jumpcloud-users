---

JumpCloud Suspended User Cleanup

Overview

This repository contains two Python scripts for automating the cleanup of suspended users in JumpCloud.
The scripts identify users who are suspended and not in the "DO NOT DELETE" (DND) group, then either list them (safe preview mode) or delete them via the JumpCloud API.
	•	list-users-to-delete.py – Safe, read-only. Lists candidates and posts an actionable Slack notice with the deletion date.
	•	delete-users.py – Production cleanup. Unbinds users from devices, deletes candidates, and posts results to Slack.

---

How It Works

Deletion requires all three conditions to be true:
1. User is marked **suspended** in JumpCloud
2. User is **not** a member of the `DO NOT DELETE` group
3. User has been suspended for **14+ days** (verified via the JumpCloud Directory Insights API)

If no suspension event is found in the Directory Insights log (e.g., the account was suspended before the 90-day DI retention window), the user is included as a candidate — conservative default.

---

Two-Step Monthly Workflow

| Week | Workflow | Schedule |
|------|----------|----------|
| Week 1 | List script runs — posts candidates to Slack | First Monday of the month, 14:00 UTC |
| Week 2 | Delete script runs — acts on current candidates | Second Monday of the month, 14:00 UTC |

Teams have one week after the list notification to add any user to the `DO NOT DELETE` group in JumpCloud to prevent deletion. The delete script re-evaluates candidates independently — it does not rely on the list from the prior week — so any user added to DND in the interim will be excluded automatically.

---

Features
	•	Automatically fetches all JumpCloud users and members of the DND group.
	•	Excludes all members of the DND group from deletion.
	•	Checks suspension age via JumpCloud Directory Insights before acting.
	•	Slack notifications with actionable messaging and deletion date.
	•	Debug logging option for troubleshooting (set DEBUG=true).
	•	Designed for hands-off execution in GitHub Actions.

---

Requirements
	•	Python 3.11+
	•	requests library (pip install -r requirements.txt)
	•	JumpCloud admin API key with permission to:
	•	List system users
	•	List group members
	•	Read Directory Insights events
	•	Delete system users (delete script only)
	•	Slack Incoming Webhook (optional but recommended)

---

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
DND_GROUP_ID	JumpCloud group ID for the "DO NOT DELETE" group
SLACK_WEBHOOK_URL	Slack Incoming Webhook URL
DEBUG (optional)	Set to true for verbose logging
SUSPENSION_MIN_AGE_DAYS (optional)	Minimum days suspended before a user is a candidate. Default: 14


---

Running Locally

List Mode (safe preview):

python list-users-to-delete.py

Delete Mode (production):

python delete_users.py


---

GitHub Actions Automation

Two workflows run automatically each month:

**test-list.yml** — first Monday, 14:00 UTC. Lists candidates and posts to Slack with the deletion date and DND instructions.

**delete-jumpcloud-users.yml** — second Monday, 14:00 UTC. Re-evaluates candidates and deletes those who still meet all criteria. Both workflows also support manual `workflow_dispatch` triggers.

---

Slack Output Example

List Script (Week 1):

*JumpCloud Suspended User Review — deletion scheduled for Monday, June 09, 2026:*
The following users have been suspended for 14+ days and are NOT in the `DO NOT DELETE` group.
They will be permanently deleted on Monday, June 09, 2026 unless added to the `DO NOT DELETE` group in JumpCloud.

*To prevent deletion:* Add the user to the `DO NOT DELETE` group before the deletion date.

- user1@example.com
- user2@example.com

Delete Script (Week 2):

*JumpCloud User Deletion Report:*
The following suspended users (NOT in `DO NOT DELETE`, suspended 14+ days) were unbound from all devices and deleted:
- user1@example.com ✅
- user2@example.com ✅

*Device Unbind Details:*
  Unbound device `MacBook-Pro` (abc123) from user1@example.com


---

Safety Notes
	•	Always run the list script first to verify candidates before enabling deletion.
	•	Both scripts use identical filtering criteria — the list output reflects exactly what the delete script will act on that same week.
	•	The 14-day suspension age check uses JumpCloud Directory Insights. If DI has no record of the suspension event (account suspended before the 90-day retention window), the user is included as a candidate.
	•	Deleted JumpCloud users cannot be restored — coordinate with HR and IT before enabling automatic deletion.
	•	Keep at least one test account in the DND group to verify exclusion logic.

---

License

This repository is for internal use within Unicity International and is not licensed for public redistribution.

---
