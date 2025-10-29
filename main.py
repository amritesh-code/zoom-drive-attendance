import os
import io
import re
import csv
import math
import requests
import urllib.parse
from datetime import date, datetime, timedelta
from dotenv import load_dotenv
from authorize import get_google_creds
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

load_dotenv()

ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID")
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")
ZOOM_ADMIN_EMAIL = os.getenv("ZOOM_ADMIN_EMAIL")

DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET_JSON", "client_secret.json")
TOKEN_FILE = os.getenv("GOOGLE_TOKEN_JSON", "token.json")


def google_creds():
    return get_google_creds(CLIENT_SECRET, TOKEN_FILE)


def zoom_access_token():
    url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ZOOM_ACCOUNT_ID}"
    resp = requests.post(url, auth=(ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET))
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_meetings(token, day):
    url = f"https://api.zoom.us/v2/report/users/{ZOOM_ADMIN_EMAIL}/meetings?from={day}&to={day}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json().get("meetings", [])


def get_participants_csv(token, meeting_id):
    encoded_id = urllib.parse.quote(meeting_id, safe="")
    url = f"https://api.zoom.us/v2/past_meetings/{encoded_id}/participants?page_size=500&include_bots=true"
    headers = {"Authorization": f"Bearer {token}", "Zoom-API-Version": "2.0.0"}

    all_participants = []
    next_page_token = ""

    while True:
        paged_url = url + (f"&next_page_token={next_page_token}" if next_page_token else "")
        r = requests.get(paged_url, headers=headers)
        r.raise_for_status()
        data = r.json()
        all_participants.extend(data.get("participants", []))
        next_page_token = data.get("next_page_token", "")
        if not next_page_token:
            break

    grouped = {}

    for p in all_participants:
        name = (p.get("name") or p.get("user_name") or "").strip()
        email = (p.get("user_email") or "").strip()
        pid = str(p.get("id") or p.get("participant_user_id") or "").strip()
        dur = int(p.get("duration", 0) or 0)

        if not name and not email:
            continue

        key = ("email", email.lower()) if email else ("name", name.lower())

        if key not in grouped:
            grouped[key] = {
                "names": set(),
                "email": email,
                "participant_ids": set(),
                "total_seconds": 0,
            }

        g = grouped[key]
        g["names"].add(name)
        g["participant_ids"].add(pid)
        g["total_seconds"] += dur
        if not g["email"] and email:
            g["email"] = email

    pid_to_emailkey = {}
    for ek, entry in grouped.items():
        if ek[0] == "email":
            for pid in entry["participant_ids"]:
                pid_to_emailkey[pid] = ek

    merge_targets = []
    for key, entry in list(grouped.items()):
        if key[0] == "name":
            hits = {pid_to_emailkey.get(pid) for pid in entry["participant_ids"] if pid in pid_to_emailkey}
            hits.discard(None)
            if hits:
                ek = next(iter(hits))
                tgt = grouped[ek]
                tgt["names"].update(entry["names"])
                tgt["participant_ids"].update(entry["participant_ids"])
                tgt["total_seconds"] += entry["total_seconds"]
                merge_targets.append(key)

    for k in merge_targets:
        grouped.pop(k, None)

    PAT_A = re.compile(r'^[AB]_')
    PAT_B = re.compile(r'_\d{4}$')
    PAT_C = re.compile(r'[_-]')
    PAT_D = re.compile(r'\([^)]*\)')

    def extract_core(name):
        c = PAT_A.sub("", name)
        c = PAT_B.sub("", c)
        c = PAT_C.sub(" ", c)
        c = PAT_D.sub("", c)
        parts = [w for w in c.split() if len(w) > 2 and not w.isdigit()]
        return parts[0].lower() if parts else ""

    name_keys = [k for k in grouped.keys() if k[0] == "name"]
    coremap = {}
    for k in name_keys:
        n = next(iter(grouped[k]["names"]), "")
        core = extract_core(n)
        if not core:
            continue
        coremap.setdefault(core, []).append(k)

    for core, keys in coremap.items():
        if len(keys) < 2:
            continue
        base = grouped[keys[0]]
        for k in keys[1:]:
            e = grouped[k]
            base["names"].update(e["names"])
            base["participant_ids"].update(e["participant_ids"])
            base["total_seconds"] += e["total_seconds"]
            grouped.pop(k, None)

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["Name (original name)", "Email", "Total duration (minutes)", "Guest"])

    def pick_display(names):
        n = list(names)
        if len(n) == 1:
            return n[0]
        s_names = [x for x in n if re.search(r'[_\d]|^[AB]_', x)]
        h_names = [x for x in n if not re.search(r'[_\d]|^[AB]_', x)]
        if s_names and h_names:
            return f"{s_names[0]} ({h_names[0]})"
        elif len(n) >= 2:
            return f"{n[0]} ({n[1]})"
        return n[0]

    entries = []
    for e in grouped.values():
        name = pick_display(e["names"])
        email = e["email"]
        minutes = math.ceil(e["total_seconds"] / 60)
        guest = "Yes" if not email or "@islorg.com" not in email.lower() else "No"
        entries.append([name, email, minutes, guest])

    entries.sort(key=lambda x: x[0].lower())
    writer.writerows(entries)

    buf.seek(0)
    return io.BytesIO(buf.getvalue().encode("utf-8"))


def upload_to_drive(creds, file_bytes, filename):
    drive_service = build("drive", "v3", credentials=creds)
    meta = {"name": filename, "parents": [DRIVE_FOLDER_ID]}
    media = MediaIoBaseUpload(file_bytes, mimetype="text/csv", resumable=False)
    drive_service.files().create(body=meta, media_body=media, fields="id").execute()


def main():
    #today = "2025-10-28"
    today = date.today().isoformat()
    print(f"Processing meetings for {today}")
    creds = google_creds()
    token = zoom_access_token()
    meetings = get_meetings(token, today)
    if not meetings:
        return
    meeting = max(meetings, key=lambda m: m.get("participants_count", 0))
    csv_data = get_participants_csv(token, meeting["uuid"])
    if not csv_data:
        return
    file_date = (date.fromisoformat(today) - timedelta(days=1)).strftime("%Y_%m_%d")
    filename = f"participants_{meeting['id']}_{file_date}.csv"
    upload_to_drive(creds, csv_data, filename)

if __name__ == "__main__":
    main()
