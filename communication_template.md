Subject: ⚠️ Automated JumpCloud Cleanup: Monthly Suspended User Deletion Notice

Hi Team,

Starting this month, our JumpCloud user cleanup process will run automatically once per month as part of our ongoing efforts to streamline user management and improve security hygiene.

🔁 What It Does:
	•	Identifies users in JumpCloud who are:
	•	Marked as suspended, and
	•	Not part of the DO NOT DELETE user group
	•	Unbinds them from all associated devices
	•	Permanently deletes them from JumpCloud
	•	Sends a confirmation to Slack with the deleted users and device unbinding details

✅ What You Need To Do:

If there are users who should not be deleted, please ensure they are added to the DO NOT DELETE user group before the script runs each month.

This is the only exclusion mechanism the system will honor. Any suspended users not in the group will be deleted automatically.

📅 Schedule:
	•	Runs automatically on the first day of each month
	•	Summary report is sent to Slack (#tmoney-test)

Let me know if you have any questions or concerns. If you need help adding users to the DO NOT DELETE group, I’m happy to assist.

Best,
Your Name
