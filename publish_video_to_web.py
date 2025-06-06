import os
import argparse
import re
import time
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaUploadProgress
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
from tqdm import tqdm

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_authenticated_service():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    return build("youtube", "v3", credentials=creds)

def parse_text_file(text_file):
    with open(text_file, "r", encoding="utf-8") as f:
        content = f.read()

    title_match = re.search(r"@(.+)", content)
    description_match = re.search(r"\*(.+)", content, re.DOTALL)

    title = title_match.group(1).strip() if title_match else "No Title"
    description = description_match.group(1).strip() if description_match else "No Description"

    return title, description

def upload_video(youtube, file_path, title, description, thumbnail):
    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": [],
            "categoryId": "22"  # People & Blogs
        },
        "status": {
            "privacyStatus": "public"
        }
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/*")
    request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media)

    response = None
    pbar = tqdm(total=100, desc="Uploading", unit="%")

    def callback(request_id, response, exception):
        if exception:
            print(f"Upload failed: {exception}")
        else:
            print(f"\nVideo ID: {response['id']}")

    progress = 0
    while response is None:
        status, response = request.next_chunk()
        if status:
            new_progress = int(status.progress() * 100)
            pbar.update(new_progress - progress)
            progress = new_progress
        time.sleep(1)

    pbar.close()

    if response:
        youtube.thumbnails().set(
            videoId=response["id"],
            media_body=thumbnail
        ).execute()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload video to YouTube.")
    parser.add_argument("video_file", help="Path to video file (e.g. Pt1.mp4)")
    parser.add_argument("-ytd", "--youtube_description", help="Text file with @title and *description")
    parser.add_argument("-ytc", "--youtube_thumbnail", help="Path to thumbnail image file (e.g. Pt1_yt_cover.jpg)")

    args = parser.parse_args()

    title, description = parse_text_file(args.youtube_description)

    youtube = get_authenticated_service()

    upload_video(youtube, args.video_file, title, description, args.youtube_thumbnail)