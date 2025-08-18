import os
import requests
from datetime import datetime, timedelta

API_KEY = os.environ["JUMPCLOUD_API_KEY"]
DND_GROUP_ID = os.environ["DND_GROUP_ID"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]
BASE_URL = "https://console.jumpcloud.com/api"
HEADERS = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}
cutoff_date = datetime.utcnow() - timedelta(days=90)

def get_all_users():
    users = []
    url = f"{BASE_URL}/systemusers"
    params = {'limit': 100, 'skip': 0}
    while True:
        res = requests.get(url, headers=HEADERS, params=params)
        res.raise_for_status()
        data = res.json()
        users.extend(data.get("results", data))
        if len(data.get("results", data)) < 100:
            break
        params['skip'] += 100
    return users

def get_dnd_group_user_ids():
    user_ids = set()
    url = f"{BASE_URL}/v2/usergroups/{DND_GROUP_ID}/members"
    params = {"limit": 100, "skip": 0}
    while True:
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json()
        for member in data:
            to = member.get("to", {})
            if to.get("type") == "user":
                user_ids.add(to.get("id"))
        if len(data) < 100:
            break
        params["skip"] += 100
    return user_ids

def unbind_user_devices(user_id, email):
    url = f"{BASE_URL}/v2/systemusers/{user_id}/computers"
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    devices = res.json()
    unbind_logs = []
    for device in devices:
        device_id = device.get("id")
        hostname = device.get("hostname", "<unknown-host>")
        if device_id:
            unbind_url = f"{BASE_URL}/v2/systemusers/{user_id}/computers/{device_id}"
            delete_res = requests.delete(unbind_url, headers=HEADERS)
            log = f"🔌 Unbound device `{hostname}` ({device_id}) from user {email}"
            print(log)
            unbind_logs.append(log)
    return unbind_logs

def delete_user(user_id):
    res = requests.delete(f"{BASE_URL}/systemusers/{user_id}", headers=HEADERS)
    print(f"🗑️ Deleted user {user_id}: {res.status_code}")

def send_slack_message(message):
    payload = {"text": message}
    res = requests.post(SLACK_WEBHOOK_URL, headers={"Content-Type": "application/json"}, json=payload)
    if res.status_code != 200:
        print(f"Failed to send Slack message: {res.status_code} - {res.text}")

def main():
    dnd_ids = get_dnd_group_user_ids()
    users = get_all_users()
    slack_logs = []

    for user in users:
        user_id = user["_id"]
        email = user.get("email", "<no-email>")
        suspended = user.get("suspended", False)
        last_login = user.get("lastLogin")

        if not suspended or not last_login:
            continue

        last_login_date = datetime.strptime(last_login, "%Y-%m-%dT%H:%M:%S.%fZ")
        if last_login_date > cutoff_date:
            continue
        if user_id in dnd_ids:
            continue

        # Unbind and log actions
        unbind_logs = unbind_user_devices(user_id, email)
        slack_logs.extend(unbind_logs)

        # Delete user and log
        delete_user(user_id)
        slack_logs.append(f"🗑️ Deleted user: `{email}`")

    # Slack output
    if slack_logs:
        message = "*JumpCloud Deletion & Unbind Summary:*\n" + "\n".join(slack_logs)
    else:
        message = "✅ No suspended users deleted (all were either active or in `DO NOT DELETE`)."

    print(message)
    send_slack_message(message)

if __name__ == "__main__":
    main()
