import os
import requests
import json

# Setup
API_KEY = os.environ["JUMPCLOUD_API_KEY"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]
DND_GROUP_ID = os.environ["DND_GROUP_ID"]
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

BASE_URL = "https://console.jumpcloud.com/api"
HEADERS = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def get_all_users():
    users = []
    url = f"{BASE_URL}/systemusers"
    params = {"limit": 100, "skip": 0}
    while True:
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()

        data = resp.json()

        if not isinstance(data, list):
            raise ValueError(f"Expected list of users but got: {type(data).__name__} — {data}")

        users.extend(data)

        if len(data) < params["limit"]:
            break
        params["skip"] += params["limit"]

    return users

def get_dnd_group_user_ids():
    user_ids = set()
    url = f"{BASE_URL}/v2/usergroups/{DND_GROUP_ID}/members"
    params = {"type": "user", "limit": 100, "skip": 0}
    while True:
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise ValueError("Expected a list of members")
        user_ids.update(member["id"] for member in data if member.get("type") == "user")
        if len(data) < params["limit"]:
            break
        params["skip"] += params["limit"]
    if DEBUG:
        print(f"📦 Retrieved {len(user_ids)} members from DND group")
    return user_ids

def identify_suspended_candidates(dnd_ids):
    candidates = []
    for user in get_all_users():
        user_id = user.get("_id")
        email = user.get("email", "<no-email>")
        suspended = user.get("suspended", False)

        if DEBUG:
            print(f"Evaluating: {email} | Suspended: {suspended}")

        if not suspended:
            continue
        if user_id in dnd_ids:
            if DEBUG:
                print(f"🔒 Skipping {email} — in DO NOT DELETE group")
            continue
        candidates.append({"email": email})
    return candidates

def send_slack_message(message):
    if not SLACK_WEBHOOK_URL:
        print("⚠️ SLACK_WEBHOOK_URL not set. Skipping Slack notification.")
        return
    payload = {"text": message}
    resp = requests.post(SLACK_WEBHOOK_URL, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
    if resp.status_code != 200:
        print(f"❌ Failed to send Slack message: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    dnd_ids = get_dnd_group_user_ids()
    candidates = identify_suspended_candidates(dnd_ids)

    if candidates:
        msg = "*JumpCloud Suspended User Review:*\nThe following users are suspended and NOT in `DO NOT DELETE` group:\n"
        msg += "\n".join([f"- {c['email']}" for c in candidates])
    else:
        msg = "✅ No suspended users eligible for deletion (all are either active or in `DO NOT DELETE`)."

    print(msg)
    send_slack_message(msg)
