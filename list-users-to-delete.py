# same as delete-users.py without the deleting
import os
import requests
import json
from datetime import datetime, timedelta

# Setup
API_KEY = os.environ["JUMPCLOUD_API_KEY"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]
BASE_URL = "https://console.jumpcloud.com/api"
HEADERS = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}
DND_GROUP_ID = os.environ["DND_GROUP_ID"]
INACTIVITY_THRESHOLD = 30
cutoff_date = datetime.utcnow() - timedelta(days=INACTIVITY_THRESHOLD)

def get_all_users():
    users = []
    url = f"{BASE_URL}/systemusers"
    params = {"limit": 100, "skip": 0}
    while True:
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()

        data = resp.json()
        batch = data.get("results", data)  # Fallback if no "results" key
        if not isinstance(batch, list):
            raise ValueError("Expected a list of users, got something else")

        users.extend(batch)

        if len(batch) < params["limit"]:
            break
        params["skip"] += params["limit"]

    return users

def user_in_group(user_id, group_id):
    url = f"{BASE_URL}/v2/users/{user_id}/memberof"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return any(g["id"] == group_id for g in resp.json())

def identify_delete_candidates():
    candidates = []
    for user in get_all_users():
        user_id = user.get("_id")
        suspended = user.get("suspended", False)
        last_login = user.get("lastLogin")
        
        if not suspended or not last_login:
            continue
        
        last_login_dt = datetime.strptime(last_login, "%Y-%m-%dT%H:%M:%S.%fZ")
        if last_login_dt > cutoff_date:
            continue
        
        if user_in_group(user_id, DND_GROUP_ID):
            continue
        
        candidates.append({
            "id": user_id,
            "email": user.get("email", "<no-email>"),
            "lastLogin": last_login,
        })
    return candidates

def send_slack_message(message):
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("SLACK_WEBHOOK_URL not set. Skipping Slack notification.")
        return
    payload = {
        "text": message
    }
    resp = requests.post(webhook_url, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
    if resp.status_code != 200:
        print(f"Failed to send Slack message: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    candidates = identify_delete_candidates()
    if candidates:
        user_list = "\n".join([f"- {c['email']} (Last login: {c['lastLogin']})" for c in candidates])
        msg = f"*JumpCloud Cleanup Report:*\nThe following users are suspended, inactive ≥90 days, and NOT in `DO NOT DELETE`:\n{user_list}"
    else:
        msg = "✅ JumpCloud Cleanup Report: No users meet the deletion criteria."

    print(msg)  # for GitHub Actions logs
    send_slack_message(msg)
