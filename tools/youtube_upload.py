#!/usr/bin/env python3
"""Upload a Holy Chip video to the YouTube channel (@holy-chip).

    youtube_upload.py VIDEO.mp4 --title "..." --description "..." [--tags "a,b,c"]
                      [--lang en|pt] [--privacy public|unlisted|private] [--playlist ID]
    youtube_upload.py --auth            # one-time: browser consent, stores the token

Vertical videos up to 3 minutes are listed as Shorts automatically. Setup
(one-time, by the user): Google Cloud project -> enable "YouTube Data API v3"
-> OAuth consent screen (External, add yourself as a test user) -> Credentials
-> OAuth client ID, type "Desktop app" -> download the JSON to
~/claude-agent/youtube_client_secret.json. Then `--auth` once (log in as the
owner of @holy-chip and pick that channel). Token: ~/claude-agent/youtube_token.json.
An upload costs 1,600 of the 10,000 daily quota units (6 uploads a day).
"""
import argparse, json, os, sys
from pathlib import Path

SECRET = Path.home() / "claude-agent" / "youtube_client_secret.json"
TOKEN = Path.home() / "claude-agent" / "youtube_token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]


def creds():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    c = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if c and c.expired and c.refresh_token:
        c.refresh(Request()); TOKEN.write_text(c.to_json())
    if not c or not c.valid:
        if not SECRET.exists():
            sys.exit(f"missing {SECRET} - create an OAuth Desktop client in Google Cloud and download its JSON there")
        from google_auth_oauthlib.flow import InstalledAppFlow
        c = InstalledAppFlow.from_client_secrets_file(str(SECRET), SCOPES).run_local_server(port=0, prompt="consent")
        TOKEN.write_text(c.to_json()); print(f"token saved: {TOKEN}")
    return c


def service():
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=creds())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?")
    ap.add_argument("--auth", action="store_true")
    ap.add_argument("--title"); ap.add_argument("--description", default="")
    ap.add_argument("--tags", default="HolyChip,AI,AGI,comics")
    ap.add_argument("--lang", default="en"); ap.add_argument("--privacy", default="public")
    ap.add_argument("--playlist"); ap.add_argument("--category", default="23")       # 23 = Comedy
    a = ap.parse_args()
    yt = service()
    if a.auth:
        me = yt.channels().list(part="snippet", mine=True).execute()["items"][0]["snippet"]
        print(f"authorized for channel: {me['title']}  ({me.get('customUrl', '')})"); return 0
    if not a.video or not a.title:
        ap.error("VIDEO and --title are required")
    from googleapiclient.http import MediaFileUpload
    body = {"snippet": {"title": a.title[:100], "description": a.description[:5000], "tags": [t.strip() for t in a.tags.split(",") if t.strip()],
                        "categoryId": a.category, "defaultLanguage": a.lang, "defaultAudioLanguage": "pt-BR" if a.lang == "pt" else "en"},
            "status": {"privacyStatus": a.privacy, "selfDeclaredMadeForKids": False}}
    media = MediaFileUpload(a.video, chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status: print(f"  upload {int(status.progress() * 100)}%", flush=True)
    vid = resp["id"]; print(f"YT_VIDEO_ID:{vid}"); print(f"YT_URL:https://youtube.com/shorts/{vid}")
    if a.playlist:
        yt.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": a.playlist, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
        print(f"  added to playlist {a.playlist}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
