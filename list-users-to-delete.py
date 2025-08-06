import os
import requests
import json
from datetime import datetime, timedelta
from dateutil import parser

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
INACTIVITY_THRESHOLD = int(os.getenv("INACTIVITY_THRESHOLD", 90))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
cutoff_date = datetime.utcnow() - timedelta(days=INACTIVITY_THRESHOLD)

def get_all_users():
    users = []
    url = f"{BASE_URL}/systemusers"
    params = {"limit": 100, "skip": 0}
    while True:
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()

        data = resp.json()
        batch = data.get("results", data)  # fallback for older API responses
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
    all_users = get_all_users()

    for user in all_users:
        user_id = user.get("_id")
        email = user.get("email", "<no-email>")
        suspended = user.get("suspended", False)
        last_login = user.get("lastLogin")

        if DEBUG:
            print(f"Evaluating: {email} | Suspended: {suspended} | Last Login: {last_login}")

        if not suspended or not last_login:
            continue

        try:
            last_login_dt = parser.isoparse(last_login)
        except Exception as e:
            if DEBUG:
                print(f"⚠️ Skipping {email} due to unparsable lastLogin: {last_login}")
            continue

        if last_login_dt > cutoff_date:
            continue

        if user_in_group(user_id, DND_GROUP_ID):
            if DEBUG:
                print(f"🔒 Skipping {email} (in DO NOT DELETE group)")
            continue

        candidates.append({
            "id": user_id,
            "email": email,
            "lastLogin": last_login,
        })

    return candidates

def send_slack_message(message):
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL not set. Skipping Slack notification.")
        return
    payload = {
        "text": message
    }
    resp = requests.post(SLACK_WEBHOOK_URL, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
    if resp.status_code != 200:
        print(f"❌ Failed to send Slack message: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    candidates = identify_delete_candidates()
    if candidates:
        user_list = "\n".join([f"- {c['email']} (Last login: {c['lastLogin']})" for c in candidates])
        msg = (
            f"*JumpCloud Cleanup Report:*\n"
            f"The following users are suspended, inactive ≥{INACTIVITY_THRESHOLD} days, "
            f"and NOT in `DO NOT DELETE` group:\n{user_list}"
        )
    else:
        msg = f"✅ JumpCloud Cleanup Report: No users meet the deletion criteria for ≥{INACTIVITY_THRESHOLD} days."

    print(msg)
    send_slack_message(msg)
