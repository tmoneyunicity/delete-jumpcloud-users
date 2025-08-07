import os
import requests
import json

# Setup
API_KEY = os.environ["JUMPCLOUD_API_KEY"]
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
BASE_URL = "https://console.jumpcloud.com/api"
HEADERS = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}
DND_GROUP_ID = os.environ["DND_GROUP_ID"]
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

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

def get_dnd_group_members(group_id):
    members = set()
    url = f"{BASE_URL}/v2/usergroups/{group_id}/members"
    params = {"limit": 100, "skip": 0}

    while True:
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json()

        for member in data:
            if member.get("type") == "user":
                members.add(member.get("id"))

        if len(data) < params["limit"]:
            break
        params["skip"] += params["limit"]
    return members

def send_slack_message(message):
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL not set. Skipping Slack notification.")
        return
    payload = { "text": message }
    resp = requests.post(SLACK_WEBHOOK_URL, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
    if resp.status_code != 200:
        print(f"❌ Failed to send Slack message: {resp.status_code} - {resp.text}")

def list_suspended_users():
    candidates = []
    all_users = get_all_users()
    dnd_members = get_dnd_group_members(DND_GROUP_ID)

    for user in all_users:
        user_id = user.get("_id")
        email = user.get("email", "<no-email>")
        suspended = user.get("suspended", False)

        if DEBUG:
            print(f"Evaluating: {email} | Suspended: {suspended}")

        if not suspended:
            continue

        if user_id in dnd_members:
            if DEBUG:
                print(f"🔒 Skipping {email} — in DO NOT DELETE group")
            continue

        candidates.append({
            "id": user_id,
            "email": email
        })

    return candidates

if __name__ == "__main__":
    candidates = list_suspended_users()
    if candidates:
        user_list = "\n".join([f"- {c['email']}" for c in candidates])
        msg = (
            f"*JumpCloud Suspended User Review:*\n"
            f"The following users are suspended and NOT in `DO NOT DELETE` group:\n{user_list}"
        )
    else:
        msg = "✅ No suspended users found outside of the DO NOT DELETE group."

    print(msg)
    send_slack_message(msg)
