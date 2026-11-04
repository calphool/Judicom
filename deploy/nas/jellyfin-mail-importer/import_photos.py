#!/usr/bin/env python3

import imaplib
import email
import os
import re
import hashlib
from email.header import decode_header
from pathlib import Path
from rapidfuzz import process, fuzz
import requests

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".heic", ".heif", ".tif", ".tiff",
    ".bmp", ".mp4", ".mov"
}

def refresh_jellyfin(url, api_key, library_id=None):
    try:
        if library_id:
            endpoint = f"{url}/Items/{library_id}/Refresh"
            params = {
                "Recursive": "true",
                "MetadataRefreshMode": "Default",
                "ImageRefreshMode": "Default",
                "ReplaceAllMetadata": "false",
                "ReplaceAllImages": "false"
            }
        else:
            endpoint = f"{url}/Library/Refresh"
            params = {}

        response = requests.post(
            endpoint,
            headers={"X-Emby-Token": api_key},
            params=params,
            timeout=30
        )

        if response.status_code in (200, 204):
            print("Jellyfin library refresh triggered successfully")
        else:
            print(f"Jellyfin refresh returned status {response.status_code}: {response.text}")

    except Exception as e:
        print(f"Failed to refresh Jellyfin: {e}")


def load_env(path):
    values = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values

def decode_mime_header(value):
    if not value:
        return ""

    parts = decode_header(value)
    decoded = ""

    for part, enc in parts:
        if isinstance(part, bytes):
            decoded += part.decode(enc or "utf-8", errors="replace")
        else:
            decoded += part

    return decoded.strip()

def safe_filename(name):
    name = os.path.basename(name)
    name = re.sub(r"[^\w.\- ()\[\]]+", "_", name)
    return name[:180] or "attachment"

def sha1_bytes(data):
    return hashlib.sha1(data).hexdigest()

def unique_path(folder, filename, digest):
    base = Path(filename).stem
    ext = Path(filename).suffix.lower()

    candidate = folder / filename

    if not candidate.exists():
        return candidate

    return folder / f"{base}_{digest[:10]}{ext}"

def choose_folder(subject, photo_root, fallback_name, threshold):
    folders = [p.name for p in photo_root.iterdir() if p.is_dir()]

    fallback = photo_root / fallback_name
    fallback.mkdir(parents=True, exist_ok=True)

    if not subject.strip() or not folders:
        return fallback, 0, fallback_name

    match = process.extractOne(
        subject,
        folders,
        scorer=fuzz.WRatio,
        processor=str.lower
    )

    if not match:
        return fallback, 0, fallback_name

    folder_name, score, _ = match

    if score >= threshold:
        return photo_root / folder_name, score, folder_name

    return fallback, score, fallback_name

def main():
    env = load_env("/home/pi/jellyfin-mail-importer/config.env")
    
    jellyfin_url = env.get("JELLYFIN_URL")
    jellyfin_api_key = env.get("JELLYFIN_API_KEY")
    jellyfin_library_id = env.get("JELLYFIN_LIBRARY_ID")

    gmail_user = env["GMAIL_USER"]
    gmail_password = env["GMAIL_APP_PASSWORD"]

    photo_root = Path(env["PHOTO_ROOT"])

    fallback_name = env.get("FALLBACK_FOLDER", "Misc")
    threshold = int(env.get("MATCH_THRESHOLD", "70"))

    print("Connecting to Gmail...")

    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(gmail_user, gmail_password)

    mail.select("INBOX")

    status, data = mail.search(None, "UNSEEN")

    if status != "OK":
        print("No unread messages found.")
        return

    message_ids = data[0].split()

    print(f"Found {len(message_ids)} unread messages")
    overall_saved = False
    for msg_id in message_ids:
        status, msg_data = mail.fetch(msg_id, "(RFC822)")

        if status != "OK":
            continue

        msg = email.message_from_bytes(msg_data[0][1])

        subject = decode_mime_header(msg.get("Subject", ""))

        target_folder, score, matched_name = choose_folder(
            subject,
            photo_root,
            fallback_name,
            threshold
        )

        print(f"\nSubject: {subject}")
        print(f"Matched folder: {matched_name} (score={score})")

        saved_any = False

        for part in msg.walk():
            disposition = part.get_content_disposition()
            filename = part.get_filename()

            if disposition != "attachment" and not filename:
                continue

            filename = decode_mime_header(filename or "attachment")
            filename = safe_filename(filename)

            ext = Path(filename).suffix.lower()

            if ext not in ALLOWED_EXTENSIONS:
                print(f"Skipping unsupported file: {filename}")
                continue

            payload = part.get_payload(decode=True)

            if not payload:
                continue

            digest = sha1_bytes(payload)

            target_path = unique_path(
                target_folder,
                filename,
                digest
            )

            with open(target_path, "wb") as f:
                f.write(payload)

            print(f"Saved: {target_path}")

            saved_any = True

        if saved_any:
            overall_saved = True
            print("Deleting processed email from Gmail...")
            mail.store(msg_id, "+FLAGS", "\\Deleted")
        else:
            print("No usable attachments found")
            mail.store(msg_id, "+FLAGS", "\\Seen")

    if overall_saved and jellyfin_url and jellyfin_api_key:
        refresh_jellyfin(jellyfin_url, jellyfin_api_key, jellyfin_library_id)

    mail.expunge()
    mail.logout()

if __name__ == "__main__":
    main()
