import os
import requests
import json
from datetime import datetime, timedelta
from dateutil import parser

# Setup
API_KEY = os.environ.get("JUMPCLOUD_API_KEY")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
BASE_URL = "https://console.jumpcloud.com/api"
HEADERS = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}
DND_GROUP_ID = os.environ.get("DND_GROUP_ID")
INACTIVITY_THRESHOLD = int(os.getenv("INACTIVITY_THRESHOLD", 7))
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
        batch = data.get("results", data)
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

def get_last_event_timestamp(user_id):
    url = f"{BASE_URL}/v2/insights/directoryevents"
    params = {
        "filter": f"user.id:eq:{user_id}",
        "sort": "-timestamp",
        "limit": 1
    }
    try:
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        events = resp.json().get("results", [])
        if events:
            return parser.isoparse(events[0]["timestamp"])
    except Exception as e:
        if DEBUG:
            print(f"⚠️ Error fetching events for {user_id}: {e}")
    return None

def identify_delete_candidates():
    candidates = []
    all_users = get_all_users()

    for user in all_users:
        user_id = user.get("_id")
        email = user.get("email", "<no-email>")
        suspended = user.get("suspended", False)

        if DEBUG:
            print(f"Evaluating: {email} | Suspended: {suspended}")

        if not suspended:
            continue

        last_event_dt = get_last_event_timestamp(user_id)

        if DEBUG:
            print(f"Last Activity for {email}: {last_event_dt}")

        if not last_event_dt or last_event_dt > cutoff_date:
            continue

        if user_in_group(user_id, DND_GROUP_ID):
            if DEBUG:
                print(f"🔒 Skipping {email} (in DO NOT DELETE group)")
            continue

        candidates.append({
            "id": user_id,
            "email": email,
            "lastActivity": last_event_dt.isoformat() if last_event_dt else "None",
        })

    return candidates

def send_slack_message(message):
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL not set. Skipping Slack notification.")
        return
    payload = {"text": message}
    resp = requests.post(SLACK_WEBHOOK_URL, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
    if resp.status_code != 200:
        print(f"❌ Failed to send Slack message: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    candidates = identify_delete_candidates()
    if candidates:
        user_list = "\n".join([f"- {c['email']} (Last activity: {c['lastActivity']})" for c in candidates])
        msg = (
            f"*JumpCloud Cleanup Report:*\n"
            f"The following users are suspended, inactive ≥{INACTIVITY_THRESHOLD} days, "
            f"and NOT in `DO NOT DELETE` group:\n{user_list}"
        )
    else:
        msg = f"✅ JumpCloud Cleanup Report: No users meet the deletion criteria for ≥{INACTIVITY_THRESHOLD} days."

    print(msg)
    send_slack_message(msg)
