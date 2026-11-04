#!/usr/bin/env python3

import imaplib
import email
import html
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

# Pictures (not videos) that may get a caption (.meta) file for the Judicom's photo show.
CAPTION_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp"}

# The words in an email's text that become the caption: the same ones the Judicom's photos.py understands.
CAPTION_KEYS = {
    "people": "people", "names": "people", "name": "people", "who": "people",
    "relationship": "relationship", "relationships": "relationship", "relation": "relationship",
    "taken": "taken", "date": "taken", "when": "taken", "photographed": "taken",
}
CAPTION_LINE = re.compile(r"^\s*(%s)\s*[:=]\s*(.+?)\s*$" % "|".join(CAPTION_KEYS), re.IGNORECASE)
# Where the sender's own words end: a quoted reply, a forwarded message, or a signature.
END_OF_OWN_TEXT = re.compile(r"^\s*(>|-- ?$|-{5,}|_{5,}|on .+ wrote:\s*$|from:\s)", re.IGNORECASE)


def email_text(msg):
    """The text of an email (its plain-text part, or its HTML part turned into text), without the attachments."""
    plain, rich = [], []
    for part in msg.walk():
        if part.get_content_maintype() != "text" or part.get_content_disposition() == "attachment":
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        (plain if part.get_content_subtype() == "plain" else rich).append(text)
    if plain:
        return "\n".join(plain)
    text = "\n".join(rich)
    text = re.sub(r"(?is)<(script|style).*?</\1>", "", text)
    text = re.sub(r"(?i)<\s*(br|/p|/div|/li|/tr|/h\d)\b[^>]*>", "\n", text)
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def parse_caption(text):
    """{'people': ..., 'relationship': ..., 'taken': ...} from lines like "people: Ann and Joe" in the sender's own text
    (not in a quoted reply, a forwarded message or a signature).  The first line for each counts.  {} if there are none."""
    caption = {}
    for line in (text or "").splitlines():
        if END_OF_OWN_TEXT.match(line):
            break
        m = CAPTION_LINE.match(line)
        if m:
            key = CAPTION_KEYS[m.group(1).lower()]
            value = " ".join(m.group(2).split())[:200]
            if value and key not in caption:
                caption[key] = value
    return caption


def write_meta(picture, caption):
    """Write picture's .meta caption file (IMG_1234.jpg -> IMG_1234.meta) for the Judicom.  Never replaces an existing one."""
    meta = picture.with_suffix(".meta")
    if meta.exists():
        print(f"Caption file already there, not replaced: {meta}")
        return None
    lines = [f"{key}: {caption[key]}" for key in ("people", "relationship", "taken") if key in caption]
    meta.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved caption: {meta}")
    return meta


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
    # Folders whose pictures get a caption (.meta) file from the email's text (the Judicom's photo folder).
    caption_folders = {f.strip().lower() for f in env.get("CAPTION_FOLDERS", "Judi").split(",") if f.strip()}

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

        caption = parse_caption(email_text(msg)) if matched_name.lower() in caption_folders else {}
        if caption:
            print("Caption from the email: " + " | ".join(f"{k}: {v}" for k, v in caption.items()))

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

            if caption and ext in CAPTION_EXTENSIONS:
                write_meta(target_path, caption)

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
