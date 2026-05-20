import json
import os
import requests
from datetime import datetime, timedelta

API_KEY = os.environ.get("JUMPCLOUD_API_KEY")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
DND_GROUP_ID = os.environ.get("DND_GROUP_ID")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
SUSPENSION_MIN_AGE_DAYS = int(os.getenv("SUSPENSION_MIN_AGE_DAYS", "14"))

BASE_URL = "https://console.jumpcloud.com/api"
DI_URL = "https://api.jumpcloud.com/insights/directory/v1/events"
PENDING_FILE = "pending_deletion.json"
HEADERS = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def debug(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}")


def validate_env():
    missing = [name for name, val in [
        ("JUMPCLOUD_API_KEY", API_KEY),
        ("DND_GROUP_ID", DND_GROUP_ID),
        ("SLACK_WEBHOOK_URL", SLACK_WEBHOOK_URL),
    ] if not val]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")


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
        debug(f"Fetched {len(batch)} users (total so far: {len(users)})")
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
        data = resp.json()
        for member in data:
            to = member.get("to", {})
            if to.get("type") == "user" and to.get("id"):
                user_ids.add(to["id"])
        if len(data) < params["limit"]:
            break
        params["skip"] += params["limit"]
    debug(f"DND group contains {len(user_ids)} users")
    return user_ids


def get_suspension_timestamp(user_id):
    start_time = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "service": ["directory"],
        "start_time": start_time,
        "search_term": {
            "and": [
                {"event_type": "user_suspended"},
                {"resource.id": user_id},
            ]
        },
        "sort": "DESC",
        "limit": 1,
    }
    try:
        resp = requests.post(DI_URL, headers=HEADERS, json=payload)
        resp.raise_for_status()
        events = resp.json()
        if not events:
            return None
        return events[0].get("timestamp")
    except Exception as e:
        print(f"[WARN] DI API call failed for {user_id}: {e} — including as candidate")
        return None


def parse_timestamp(ts):
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized timestamp format: {ts}")


def is_old_enough(user_id, email):
    ts = get_suspension_timestamp(user_id)
    if ts is None:
        debug(f"{email}: no DI suspension event in last 90 days — including (conservative default)")
        return True
    suspended_at = parse_timestamp(ts)
    age_days = (datetime.utcnow() - suspended_at).days
    debug(f"{email}: suspended {age_days} days ago")
    return age_days >= SUSPENSION_MIN_AGE_DAYS


def identify_suspended_candidates(dnd_ids):
    candidates = []
    for user in get_all_users():
        user_id = user.get("_id")
        email = user.get("email", "<no-email>")
        suspended = user.get("suspended", False)
        if not suspended or user_id in dnd_ids:
            continue
        if not is_old_enough(user_id, email):
            debug(f"{email}: suspended less than {SUSPENSION_MIN_AGE_DAYS} days ago — skipping")
            continue
        candidates.append({"email": email, "id": user_id})
    debug(f"Found {len(candidates)} candidates after suspension age filter")
    return candidates


def save_pending_candidates(candidates):
    with open(PENDING_FILE, "w") as f:
        json.dump(candidates, f, indent=2)
    debug(f"Saved {len(candidates)} candidates to {PENDING_FILE}")


def send_slack_message(message):
    if not SLACK_WEBHOOK_URL:
        return
    resp = requests.post(SLACK_WEBHOOK_URL, headers={"Content-Type": "application/json"}, json={"text": message})
    if resp.status_code != 200:
        print(f"Slack notification failed: {resp.status_code} - {resp.text}")


def check_auth():
    resp = requests.get(f"{BASE_URL}/systemusers?limit=1", headers=HEADERS)
    if resp.status_code == 401:
        raise SystemExit(f"AUTH FAILED — JumpCloud rejected the API key (401). Response: {resp.text}")
    resp.raise_for_status()
    print("AUTH OK — API key accepted")


if __name__ == "__main__":
    validate_env()
    check_auth()
    dnd_ids = get_dnd_group_user_ids()
    candidates = identify_suspended_candidates(dnd_ids)
    save_pending_candidates(candidates)
    deletion_date = (datetime.utcnow() + timedelta(days=7)).strftime("%A, %B %d, %Y")
    if candidates:
        lines = [
            f"*JumpCloud Suspended User Review — deletion scheduled for {deletion_date}:*",
            f"The following users have been suspended for {SUSPENSION_MIN_AGE_DAYS}+ days and are NOT in the `DO NOT DELETE` group.",
            f"They will be permanently deleted on {deletion_date} unless added to the `DO NOT DELETE` group in JumpCloud.",
            "",
            "*To prevent deletion:* Add the user to the `DO NOT DELETE` group before the deletion date.",
            "",
        ]
        lines.extend([f"- {c['email']}" for c in candidates])
        msg = "\n".join(lines)
    else:
        msg = "✅ No suspended users eligible for deletion."
    print(msg)
    send_slack_message(msg)
