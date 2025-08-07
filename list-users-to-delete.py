import os
import requests
import json

# Environment variables
API_KEY = os.environ["JUMPCLOUD_API_KEY"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]
DND_GROUP_ID = os.environ["DND_GROUP_ID"]
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Setup
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

def send_slack_message(message):
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL not set. Skipping Slack notification.")
        return
    payload = { "text": message }
    resp = requests.post(SLACK_WEBHOOK_URL, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
    if resp.status_code != 200:
        print(f"❌ Failed to send Slack message: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    users = get_all_users()
    candidates = []

    for user in users:
        user_id = user.get("_id")
        email = user.get("email", "<no-email>")
        suspended = user.get("suspended", False)

        if DEBUG:
            print(f"Evaluating {email} | Suspended: {suspended}")

        if not suspended:
            continue

        try:
            if user_in_group(user_id, DND_GROUP_ID):
                if DEBUG:
                    print(f"🔒 Skipping {email} — in DO NOT DELETE group")
                continue
        except Exception as e:
            print(f"⚠️ Failed to check group for {email}: {e}")
            continue

        candidates.append(email)

    # Reporting
    if candidates:
        user_list = "\n".join([f"- {email}" for email in candidates])
        msg = (
            "*JumpCloud Cleanup Report (Test Run)*\n"
            "The following users are SUSPENDED and NOT in the `DO NOT DELETE` group. "
            "**They would be deleted in a live run:**\n"
            f"{user_list}"
        )
    else:
        msg = "✅ JumpCloud Cleanup Report (Test Run): No users match the deletion criteria."

    print(msg)
    send_slack_message(msg)
