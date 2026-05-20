---

JumpCloud Suspended User Cleanup

Overview

This repository contains two Python scripts for automating the cleanup of suspended users in JumpCloud.
The scripts identify users who are suspended and not in the "DO NOT DELETE" (DND) group, then either list them (safe preview mode) or delete them via the JumpCloud API.
	•	list-users-to-delete.py – Safe, read-only. Lists candidates, writes the frozen candidate list, and posts an actionable Slack notice with the deletion date.
	•	delete-users.py – Production cleanup. Reads the frozen candidate list, re-verifies current state, unbinds users from devices, deletes candidates, and posts results to Slack.

---

How It Works

A user is a deletion candidate if all three conditions are true:
1. User is marked **suspended** in JumpCloud
2. User is **not** a member of the `DO NOT DELETE` group
3. User has been suspended for **14+ days** (verified via the JumpCloud Directory Insights API)

If no suspension event is found in the Directory Insights log (e.g., the account was suspended before the 90-day DI retention window), the user is included as a candidate — conservative default.

---

Two-Step Monthly Workflow

| Week | Workflow | Schedule |
|------|----------|----------|
| Week 1 | List script runs — evaluates candidates, writes `pending_deletion.json`, posts Slack notice | First Monday of the month, 14:00 UTC |
| Week 2 | Delete script runs — reads `pending_deletion.json`, re-verifies state, deletes qualifying users | Second Monday of the month, 14:00 UTC |

The candidate list is **frozen at Week 1**. The delete script on Week 2 only acts on users who appeared in that specific list — no new suspensions during the intervening week are included.

The only way a listed user avoids deletion on Week 2 is if someone intervenes before the second Monday:
- Add them to the `DO NOT DELETE` group in JumpCloud, or
- Reactivate (unsuspend) their account

Either action is detected automatically — the delete script re-checks current suspension status and DND membership before acting on each candidate.

---

Features
	•	Authenticates via JumpCloud Service Account (OAuth2 client credentials).
	•	Automatically fetches all JumpCloud users and members of the DND group.
	•	Excludes all members of the DND group from deletion.
	•	Checks suspension age via JumpCloud Directory Insights before listing.
	•	Frozen candidate list ensures Week 2 deletes exactly what Week 1 reviewed.
	•	Slack notifications with actionable messaging and deletion date.
	•	Dry run mode for safe end-to-end testing without making changes.
	•	Debug logging option for troubleshooting.
	•	Designed for hands-off execution in GitHub Actions.

---

Requirements
	•	Python 3.11+
	•	requests library (pip install -r requirements.txt)
	•	JumpCloud Service Account (Manager role or higher) with a Client Secret key type
	•	JumpCloud permissions needed:
	•	List system users
	•	List user group members
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

3. Create a JumpCloud Service Account

In JumpCloud → Settings → Service Accounts → New:
- Assign Manager role or higher
- Set Key Type to Client Secret
- Copy the Client ID and Client Secret

4. Add GitHub Actions Secrets and Variables

In GitHub → Settings → Secrets and variables → Actions:

Secrets:

Secret Name	Description
JUMPCLOUD_CLIENT_ID	Client ID from the JumpCloud Service Account
JUMPCLOUD_CLIENT_SECRET	Client Secret from the JumpCloud Service Account
SLACK_WEBHOOK_URL	Slack Incoming Webhook URL
DEBUG (optional)	Set to true for verbose logging
SUSPENSION_MIN_AGE_DAYS (optional)	Minimum days suspended before a user is a candidate. Default: 14

Variables (non-sensitive):

Variable Name	Description
DND_GROUP_ID	JumpCloud group ID for the "DO NOT DELETE" group


---

Running Locally

Set environment variables first:

export JUMPCLOUD_CLIENT_ID=your-client-id
export JUMPCLOUD_CLIENT_SECRET=your-client-secret
export DND_GROUP_ID=your-group-id
export SLACK_WEBHOOK_URL=your-webhook-url

List Mode (safe preview):

python list-users-to-delete.py

Delete Mode (production):

python delete_users.py


---

GitHub Actions Automation

Two workflows run automatically each month:

**test-list.yml (List Suspended JumpCloud Users)** — first Monday, 14:00 UTC. Identifies candidates, writes `pending_deletion.json` to the repo, and posts a Slack notice with the deletion date and DND instructions. Also supports manual `workflow_dispatch`.

**delete-jumpcloud-users.yml (Delete Suspended JumpCloud Users)** — second Monday, 14:00 UTC. Reads `pending_deletion.json`, re-verifies each user's current state, and deletes those who still qualify. Clears `pending_deletion.json` after each run. Also supports manual `workflow_dispatch`.

Dry Run

The delete workflow has a **Dry run** checkbox when triggered manually via `workflow_dispatch`. When checked, the script runs the full pipeline but skips actual delete and unbind API calls, logging `[DRY RUN] Would delete: user@example.com` instead. The Slack report is labelled `[DRY RUN]`. Scheduled runs always default to dry run off.

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

*Deleted (2):*
- user1@example.com ✅
- user2@example.com ✅

*Device Unbind Details:*
  Unbound device `MacBook-Pro` (abc123) from user1@example.com

If users were protected between Week 1 and Week 2:

*Skipped — protected or changed since last review (1):*
- user3@example.com _(added to DO NOT DELETE group)_


---

Safety Notes
	•	Always run the list workflow first and review the Slack output before enabling automatic deletion.
	•	The delete script only acts on the frozen `pending_deletion.json` list from Week 1 — new suspensions during the week are never included.
	•	Use the Dry run checkbox on the delete workflow to verify the full pipeline before a real run.
	•	Deleted JumpCloud users cannot be restored — coordinate with HR and IT before enabling automatic deletion.
	•	Keep at least one test account in the DND group to verify exclusion logic.
	•	`pending_deletion.json` contains email addresses and is committed to the repo — ensure the repository remains private.

---

License

This repository is for internal use within Unicity International and is not licensed for public redistribution.

---
