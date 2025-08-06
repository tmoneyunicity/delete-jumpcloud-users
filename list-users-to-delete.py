# same as delete-jumpcloud-users.py without the deleting
import os
import requests
from datetime import datetime, timedelta

# Setup
API_KEY = os.environ["JUMPCLOUD_API_KEY"]
BASE_URL = "https://console.jumpcloud.com/api"
HEADERS = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}
DND_GROUP_ID = os.environ["DND_GROUP_ID"]
INACTIVITY_THRESHOLD = 90
cutoff_date = datetime.utcnow() - timedelta(days=INACTIVITY_THRESHOLD)

def get_all_users():
    users = []
    url = f"{BASE_URL}/systemusers"
    params = {"limit": 100, "skip": 0}
    while True:
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        batch = resp.json()
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

if __name__ == "__main__":
    candidates = identify_delete_candidates()
    if candidates:
        print("The following users are suspended, inactive ≥90 days, and NOT in 'DO NOT DELETE':\n")
        for c in candidates:
            print(f"- {c['email']} (Last login: {c['lastLogin']})")
    else:
        print("No candidates found for deletion.")
