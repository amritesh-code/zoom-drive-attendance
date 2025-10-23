from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os, json

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

def get_google_creds(client_secret, token_file):
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w") as t:
            t.write(creds.to_json())
    return creds

if __name__ == "__main__":
    get_google_creds("client_secret.json", "token.json")
