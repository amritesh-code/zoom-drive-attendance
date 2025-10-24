# Zoom Attendance Automation to Google Drive  

Automated pipeline to fetch daily participant attendance reports from Zoom and upload them directly to a designated Google Drive folder in `.csv` format.  
Supports automated daily execution through GitHub Actions.

---

## Overview

This script automates:
- Authentication with Zoom Reports API (via OAuth `account_credentials` flow).  
- Retrieval of meeting participant data for the organization’s admin account.  
- Aggregation of participant durations to mimic Zoom’s native “unique users” export format.  
- Upload of each day’s attendance file to a configured Google Drive folder.  

All exports follow Zoom’s naming convention:  
```
participants_<meeting_id>_<YYYY_MM_DD>.csv

```
(`YYYY_MM_DD` is one day behind actual meeting date to match Zoom’s downloaded filenames.)


## Prerequisites

- Zoom account with **Reports API access** (admin or higher).  
- A **Google Cloud project** with Drive API enabled.  
- `client_secret.json` and valid OAuth `token.json` for the Drive account.  
- Python ≥ 3.10  

---

## Environment Variables

All secrets are stored in `.env` (locally) or GitHub Secrets (in Actions).

| Variable | Description |
|-----------|--------------|
| `ZOOM_ACCOUNT_ID` | Zoom App’s Account ID |
| `ZOOM_CLIENT_ID` | Zoom App’s Client ID |
| `ZOOM_CLIENT_SECRET` | Zoom App’s Client Secret |
| `ZOOM_ADMIN_EMAIL` | Zoom admin email (used in API endpoint) |
| `DRIVE_FOLDER_ID` | Google Drive folder where files are uploaded |
| `GOOGLE_CLIENT_SECRET_JSON` | Path to OAuth client secret file |
| `GOOGLE_TOKEN_JSON` | Path to OAuth token file |

---

## File Structure

```
zoom_to_drive/
├── main.py                 # Core logic (Zoom → Drive)
├── authorize.py            # Google OAuth helper
├── requirements.txt        # Dependencies
├── .env                    # Local environment variables
├── client_secret.json      # Google OAuth client
├── token.json              # Google access token
└── .github/workflows/
└── upload.yml          # GitHub Actions scheduler
```

---

## Local Usage

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Authorize Google Drive

```bash
python authorize.py
```

### 3. Run the upload for a single day

```bash
python main.py
```

## Automation via GitHub Actions

Workflow file: `.github/workflows/upload.yml`

Runs daily at **11:00 PM IST (17:30 UTC)**:

Secrets required:

* `ZOOM_ACCOUNT_ID`
* `ZOOM_CLIENT_ID`
* `ZOOM_CLIENT_SECRET`
* `ZOOM_ADMIN_EMAIL`
* `DRIVE_FOLDER_ID`
* `CLIENT_SECRET_JSON`
* `TOKEN_JSON`


## Notes

* Each day’s upload is unique and does not overwrite existing files.
* Meeting selected = the one with highest participant count on that date.
* CSV formatting matches Zoom’s “Show unique users” export.
* For accurate timing, Zoom’s UTC timestamps are converted internally, but filenames use Zoom’s own date offset (–1 day).

---