import json
import os
import requests

API_KEY = os.environ.get("JUMPCLOUD_API_KEY")
DND_GROUP_ID = os.environ.get("DND_GROUP_ID")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

BASE_URL = "https://console.jumpcloud.com/api"
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


def load_pending_candidates():
    if not os.path.exists(PENDING_FILE):
        return []
    with open(PENDING_FILE) as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


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


def unbind_user_devices(user_id, email):
    # GET /v2/systemusers/{id}/systems returns systems bound to the user
    url = f"{BASE_URL}/v2/systemusers/{user_id}/systems"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    devices = resp.json()
    unbind_logs = []
    for device in devices:
        device_id = device.get("id")
        hostname = device.get("displayName") or device.get("hostname", "<unknown-host>")
        if not device_id:
            continue
        # JumpCloud v2 associations API: POST with op=remove to unbind
        assoc_url = f"{BASE_URL}/v2/systemusers/{user_id}/associations"
        payload = {"op": "remove", "type": "system", "id": device_id}
        unbind_resp = requests.post(assoc_url, headers=HEADERS, json=payload)
        unbind_resp.raise_for_status()
        log = f"  Unbound device `{hostname}` ({device_id}) from {email}"
        print(log)
        unbind_logs.append(log)
    return unbind_logs


def delete_user(user_id, email):
    resp = requests.delete(f"{BASE_URL}/systemusers/{user_id}", headers=HEADERS)
    if resp.status_code == 404:
        print(f"  {email} already removed from JumpCloud — skipping")
        return
    resp.raise_for_status()
    print(f"  Deleted user: {email} ({user_id})")


def send_slack_message(message):
    if not SLACK_WEBHOOK_URL:
        return
    resp = requests.post(SLACK_WEBHOOK_URL, headers={"Content-Type": "application/json"}, json={"text": message})
    if resp.status_code != 200:
        print(f"Failed to send Slack message: {resp.status_code} - {resp.text}")


def main():
    validate_env()

    pending = load_pending_candidates()
    if not pending:
        message = "✅ No candidates from last week's review. Nothing to delete."
        print(message)
        send_slack_message(message)
        return

    # Re-fetch current state to respect changes made since the list ran
    dnd_ids = get_dnd_group_user_ids()
    all_users = get_all_users()
    current_by_id = {u["_id"]: u for u in all_users}

    deleted_lines = []
    skipped_lines = []
    unbind_lines = []

    for candidate in pending:
        user_id = candidate["id"]
        email = candidate["email"]
        user = current_by_id.get(user_id)

        if user is None:
            debug(f"{email}: no longer in JumpCloud — skipping")
            skipped_lines.append(f"- {email} _(already removed from JumpCloud)_")
            continue
        if not user.get("suspended", False):
            debug(f"{email}: no longer suspended — skipping")
            skipped_lines.append(f"- {email} _(reactivated)_")
            continue
        if user_id in dnd_ids:
            debug(f"{email}: added to DND group since last review — skipping")
            skipped_lines.append(f"- {email} _(added to DO NOT DELETE group)_")
            continue

        device_logs = unbind_user_devices(user_id, email)
        unbind_lines.extend(device_logs)
        delete_user(user_id, email)
        deleted_lines.append(f"- {email} ✅")

    parts = ["*JumpCloud User Deletion Report:*"]

    if deleted_lines:
        parts.append(f"\n*Deleted ({len(deleted_lines)}):*")
        parts.extend(deleted_lines)

    if skipped_lines:
        parts.append(f"\n*Skipped — protected or changed since last review ({len(skipped_lines)}):*")
        parts.extend(skipped_lines)

    if unbind_lines:
        parts.append("\n*Device Unbind Details:*")
        parts.extend(unbind_lines)

    if not deleted_lines and not skipped_lines:
        message = "✅ No suspended users deleted (all were either active or in `DO NOT DELETE`)."
    else:
        message = "\n".join(parts)

    print(message)
    send_slack_message(message)


if __name__ == "__main__":
    main()
