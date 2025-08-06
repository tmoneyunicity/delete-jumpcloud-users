import os
import requests
from datetime import datetime, timedelta

API_KEY = os.environ["JUMPCLOUD_API_KEY"]
DND_GROUP_ID = os.environ["DND_GROUP_ID"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]
DAYS_INACTIVE = 90
cutoff_date = datetime.utcnow() - timedelta(days=DAYS_INACTIVE)

def send_slack_notification(message):
    payload = {"text": message}
    requests.post(SLACK_WEBHOOK_URL, json=payload)

def get_all_users():
    users = []
    url = f"{BASE_URL}/systemusers"
    params = {'limit': 100, 'skip': 0}

    while True:
        res = requests.get(url, headers=HEADERS, params=params)
        res.raise_for_status()
        batch = res.json()
        users.extend(batch)
        if len(batch) < 100:
            break
        params['skip'] += 100
    return users

def user_in_group(user_id, group_id):
    res = requests.get(f"{BASE_URL}/v2/usergroups/{group_id}/members", headers=HEADERS)
    res.raise_for_status()
    group_members = res.json()
    return any(member['id'] == user_id for member in group_members)

def delete_user(user_id):
    res = requests.delete(f"{BASE_URL}/systemusers/{user_id}", headers=HEADERS)
    print(f"Deleted user {user_id}: {res.status_code}")

users = get_all_users()

for user in users:
    last_login = user.get('lastLogin')
    suspended = user.get('suspended', False)
    user_id = user['_id']

    if not suspended:
        continue

    if not last_login:
        continue

    last_login_date = datetime.strptime(last_login, "%Y-%m-%dT%H:%M:%S.%fZ")
    if last_login_date > cutoff_date:
        continue

    if user_in_group(user_id, DND_GROUP_ID):
        continue

    delete_user(user_id)
