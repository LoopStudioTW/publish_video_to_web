import os
import argparse
import re
import time
from glob import glob
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
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
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "public"
        }
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/*")
    request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media)

    response = None
    pbar = tqdm(total=100, desc="Uploading", unit="%")
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
        return response["id"]
    return None

def find_video_sets(folder):
    mp4_files = glob(os.path.join(folder, "*_yt.mp4"))
    video_sets = []

    if not mp4_files:
        print("🔍 找不到任何 *_yt.mp4 檔案")
        return []

    for mp4_file in mp4_files:
        base = os.path.basename(mp4_file).replace("_yt.mp4", "")
        txt_file = os.path.join(folder, f"{base}_yt.txt")
        jpg_file = os.path.join(folder, f"{base}_yt_cover.jpg")

        print(f"\n🔎 檢查影片組合：{base}")
        print(f"   - mp4：{'✅' if os.path.exists(mp4_file) else '❌'} {mp4_file}")
        print(f"   - txt：{'✅' if os.path.exists(txt_file) else '❌'} {txt_file}")
        print(f"   - jpg：{'✅' if os.path.exists(jpg_file) else '❌'} {jpg_file}")

        if os.path.exists(txt_file) and os.path.exists(jpg_file):
            video_sets.append((mp4_file, txt_file, jpg_file, base))
        else:
            print(f"⚠️  缺少檔案，跳過：{base}")

    return video_sets

def main(folder_path):
    youtube = get_authenticated_service()
    output_link_file = os.path.join(folder_path, "yt_link.txt")

    video_sets = find_video_sets(folder_path)
    if not video_sets:
        print("❌ 找不到任何影片組合（需包含 *_yt.mp4, *_yt.txt, *_yt_cover.jpg）")
        return

    with open(output_link_file, "w", encoding="utf-8") as f_out:
        for video_file, text_file, cover_file, base_name in video_sets:
            print(f"\n🚀 上傳中：{base_name}")
            title, description = parse_text_file(text_file)
            video_id = upload_video(youtube, video_file, title, description, cover_file)
            if video_id:
                yt_link = f"https://youtu.be/{video_id}"
                f_out.write(f"{base_name}: {yt_link}\n")
                print(f"✅ 上傳完成：{yt_link}")
            else:
                print(f"❌ {base_name} 上傳失敗")

    print(f"\n📄 所有影片連結已儲存在：{output_link_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch upload YouTube videos from folder.")
    parser.add_argument("folder", help="Path to folder containing *_yt.mp4, *_yt.txt, *_yt_cover.jpg files")
    args = parser.parse_args()
    main(args.folder)
