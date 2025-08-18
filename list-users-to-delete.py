
import os
import requests
import json

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
        batch = data.get("results", data)
        if not isinstance(batch, list):
            raise ValueError(f"Expected list of users but got: {type(batch).__name__}")
        users.extend(batch)
        if len(batch) < params["limit"]:
            break
        params["skip"] += params["limit"]
    return users

def get_dnd_group_user_ids():
    user_ids = set()
    url = f"{BASE_URL}/v2/usergroups/{DND_GROUP_ID}/members"
    params = {"limit": 100, "skip": 0}
    while True:
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        for member in resp.json():
            to = member.get("to", {})
            if to.get("type") == "user" and to.get("id"):
                user_ids.add(to["id"])
        if len(resp.json()) < params["limit"]:
            break
        params["skip"] += params["limit"]
    return user_ids

def identify_suspended_candidates(dnd_ids):
    candidates = []
    for user in get_all_users():
        user_id = user.get("_id")
        email = user.get("email", "<no-email>")
        suspended = user.get("suspended", False)
        if not suspended or user_id in dnd_ids:
            continue
        candidates.append({"email": email, "id": user_id})
    return candidates

def send_slack_message(message):
    if not SLACK_WEBHOOK_URL:
        return
    payload = {"text": message}
    resp = requests.post(SLACK_WEBHOOK_URL, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
    if resp.status_code != 200:
        print(f"Slack notification failed: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    dnd_ids = get_dnd_group_user_ids()
    candidates = identify_suspended_candidates(dnd_ids)
    if candidates:
        msg = "*JumpCloud Suspended User Review:*
The following users are suspended and NOT in `DO NOT DELETE` group:
"
        msg += "\n".join([f"- {c['email']}" for c in candidates])
    else:
        msg = "✅ No suspended users eligible for deletion."
    print(msg)
    send_slack_message(msg)
