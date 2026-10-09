import base64
import json
from email.message import EmailMessage
from pathlib import Path

from .config import Vault
from .store import Store

SCOPES = {
    "gmail": ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.compose"],
    "calendar": ["https://www.googleapis.com/auth/calendar.events"],
    "drive": ["https://www.googleapis.com/auth/drive.file"],
    "people": ["https://www.googleapis.com/auth/contacts.readonly"],
    "meet": ["https://www.googleapis.com/auth/meetings.space.readonly"],
}


class Google:
    def __init__(self, store: Store, vault: Vault):
        self.store, self.vault = store, vault

    def authorize(self):
        from google_auth_oauthlib.flow import InstalledAppFlow
        s = self.store.settings()
        path = Path(s["google_client_file"])
        if not path.is_file():
            raise ValueError("Select your private Desktop OAuth client JSON in Settings")
        scopes = [scope for service in s["google_scopes"] for scope in SCOPES[service]]
        if not scopes:
            raise ValueError("Select at least one Google integration scope")
        flow = InstalledAppFlow.from_client_secrets_file(str(path), scopes=scopes)
        credentials = flow.run_local_server(host="localhost", port=0, timeout_seconds=180, open_browser=True,
            authorization_prompt_message="Complete authorization in your browser.")
        self.vault.put("google_tokens", credentials.to_json())
        self.store.event("google_connected", "Google OAuth authorization completed")
        return {"connected": True, "scopes": scopes}

    def credentials(self):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        raw = self.vault.get("google_tokens")
        if not raw:
            raise ValueError("Google is not connected. Authorize in Settings.")
        credentials = Credentials.from_authorized_user_info(json.loads(raw))
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self.vault.put("google_tokens", credentials.to_json())
        if not credentials.valid:
            raise ValueError("Google authorization expired. Reconnect; testing-mode tokens may expire.")
        return credentials

    def service(self, name, version, scope_group):
        from googleapiclient.discovery import build
        import httplib2
        from google_auth_httplib2 import AuthorizedHttp
        credentials = self.credentials()
        if not credentials.has_scopes(SCOPES[scope_group]):
            raise ValueError(f"Reconnect Google with {scope_group} scope enabled")
        return build(name, version, http=AuthorizedHttp(credentials, http=httplib2.Http(timeout=20)), cache_discovery=False)

    def execute(self, operation: str, args: dict):
        if operation == "gmail_list":
            service = self.service("gmail", "v1", "gmail")
            result = service.users().messages().list(userId="me", q=args.get("query", "in:inbox"), maxResults=10).execute()
            return result
        if operation == "gmail_read":
            return self.service("gmail", "v1", "gmail").users().messages().get(userId="me", id=args["id"], format="full").execute()
        if operation in {"gmail_draft", "gmail_send"}:
            msg = EmailMessage()
            if any(c in args["to"] + args["subject"] for c in "\r\n"):
                raise ValueError("Invalid recipient or subject")
            msg["To"], msg["Subject"] = args["to"], args["subject"]
            msg.set_content(args["body"])
            body = {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}
            service = self.service("gmail", "v1", "gmail")
            if operation == "gmail_draft":
                return service.users().drafts().create(userId="me", body={"message": body}).execute()
            return service.users().messages().send(userId="me", body=body).execute()
        if operation == "calendar_list":
            return self.service("calendar", "v3", "calendar").events().list(calendarId="primary", maxResults=20,
                singleEvents=True, orderBy="startTime", timeMin=args["from_time"]).execute()
        if operation == "calendar_create":
            return self.service("calendar", "v3", "calendar").events().insert(calendarId="primary", body={
                "summary": args["title"], "description": args.get("description", ""),
                "start": {"dateTime": args["start"], "timeZone": args.get("timezone", "Asia/Kolkata")},
                "end": {"dateTime": args["end"], "timeZone": args.get("timezone", "Asia/Kolkata")}}).execute()
        if operation == "drive_list":
            return self.service("drive", "v3", "drive").files().list(pageSize=20, fields="files(id,name,mimeType)").execute()
        if operation == "drive_backup":
            from googleapiclient.http import MediaInMemoryUpload
            data = json.dumps(self.store.export()).encode()
            return self.service("drive", "v3", "drive").files().create(body={"name": "ultron-export.json"},
                media_body=MediaInMemoryUpload(data, mimetype="application/json"), fields="id,name").execute()
        if operation == "contacts_list":
            return self.service("people", "v1", "people").people().connections().list(resourceName="people/me",
                pageSize=50, personFields="names,emailAddresses,phoneNumbers").execute()
        if operation == "meet_recordings":
            return self.service("meet", "v2", "meet").conferenceRecords().recordings().list(parent=args["conference"]).execute()
        if operation == "meet_transcripts":
            return self.service("meet", "v2", "meet").conferenceRecords().transcripts().list(parent=args["conference"]).execute()
        raise ValueError("Unsupported Google operation")
