"""Bring the family photos from the NAS to the Judicom.   python3 -m judicom.photo_sync      (--dry-run: say what it would do)

The master folder is /mnt/8tbdrive/Photos/Judi on the NAS (shared with Jellyfin): add, change or remove pictures and their .meta
caption files there.  This makes ~/photos on the Judicom the same, with rsync over Tailscale; the photo show picks the changes up by
itself.  Run by the judicom-photo-sync timer (at boot, then every hour); run it by hand for an instant update.

It uses its own key (~/.ssh/judicom_photos), which the NAS only lets READ that one folder: on the NAS's side the key's line in
~pi/.ssh/authorized_keys is   restrict,command="/usr/bin/rrsync -ro /mnt/8tbdrive/Photos/Judi" ssh-ed25519 ...
Safety: nothing is changed when the NAS cannot be reached, when its folder has no pictures in it (a drive not mounted, say), or when
the sync would remove more than half of the pictures on the Judicom; the reason is printed (journalctl -u judicom-photo-sync).
New files are copied under hidden names and renamed when complete, so the photo show never sees half a picture.
"""
import argparse
import os
import subprocess
import sys

from . import config

MAX_DELETE_SHARE = 0.5          # refuse to remove more than this share of the Judicom's pictures in one sync


def ssh_command(key=None):
    key = key or config.PHOTO_SYNC_KEY
    return "ssh -i %s -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new" % key


def reason(stderr, code):
    """The most useful line of rsync's complaint: ssh's own message (cannot connect, key refused) beats rsync's summary line."""
    lines = [l.strip() for l in (stderr or "").splitlines() if l.strip()]
    for l in lines:
        if l.startswith("ssh:") or "Permission denied" in l or "Host key verification failed" in l or "rrsync error" in l:
            return l
    return lines[-1] if lines else "rsync exit status %d" % code


def is_picture(name):
    return os.path.splitext(name)[1].lower() in config.PHOTO_EXTS and not name.startswith(".")


def remote_files(host=None, key=None, run=subprocess.run):
    """The file names in the NAS folder (top level only), or raises RuntimeError."""
    host = host or config.SYNC_HOST
    cmd = ["rsync", "--list-only", "-e", ssh_command(key), "%s:./" % host]
    try:
        result = run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("cannot reach %s: %s" % (host, exc)) from None
    if result.returncode != 0:
        raise RuntimeError("%s: %s" % (host, reason(result.stderr, result.returncode)))
    names = []
    for line in result.stdout.splitlines():
        # "-rw-r--r--      1,707,019 2026/11/03 20:24:01 Joe_And_Amy.jpg"   (names may contain spaces)
        parts = line.split(None, 4)
        if len(parts) == 5 and parts[0].startswith("-"):
            names.append(parts[4])
    return names


def plan(remote, local_folder):
    """(to_remove, local_pictures, remote_pictures) by name; to_remove = files on the Judicom that are no longer on the NAS."""
    try:
        local = [n for n in os.listdir(local_folder) if not n.startswith(".") and os.path.isfile(os.path.join(local_folder, n))]
    except OSError:
        local = []
    remote_set = set(remote)
    to_remove = sorted(n for n in local if n not in remote_set)
    return to_remove, [n for n in local if is_picture(n)], [n for n in remote if is_picture(n)]


def check(to_remove, local_pictures, remote_pictures):
    """Raises RuntimeError if the sync must not run."""
    if not remote_pictures:
        raise RuntimeError("the NAS's photo folder has no pictures in it (is the drive mounted?)")
    removing = [n for n in to_remove if is_picture(n)]
    if local_pictures and len(removing) > MAX_DELETE_SHARE * len(local_pictures):
        raise RuntimeError("it would remove %d of the %d pictures here; if that is really wanted, run it by hand with --force"
                           % (len(removing), len(local_pictures)))


def copy(local_folder, host=None, key=None, run=subprocess.run):
    """rsync the NAS folder into local_folder; returns the list of rsync's changes ('>f+++++++++ name', '*deleting name', ...)."""
    host = host or config.SYNC_HOST
    os.makedirs(local_folder, exist_ok=True)
    cmd = ["rsync", "-rt", "--delete", "--delay-updates", "--chmod=D755,F644", "--itemize-changes",
           "-e", ssh_command(key), "%s:./" % host, local_folder.rstrip("/") + "/"]
    try:
        result = run(cmd, capture_output=True, text=True, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("the copy did not finish: %s" % exc) from None
    if result.returncode != 0:
        raise RuntimeError("the copy failed (%s)" % reason(result.stderr, result.returncode))
    return [line for line in result.stdout.splitlines() if line.strip() and not line.startswith(".d")]


def sync(local_folder=None, lister=remote_files, copier=copy, dry_run=False, force=False, log=print):
    """0: done (changed or not), 1: nothing changed (the reason is logged)."""
    local_folder = str(config.PHOTO_DIR if local_folder is None else local_folder)
    try:
        remote = lister()
        to_remove, local_pictures, remote_pictures = plan(remote, local_folder)
        if not force:
            check(to_remove, local_pictures, remote_pictures)
        elif not remote_pictures:
            raise RuntimeError("the NAS's photo folder has no pictures in it; not even --force empties the Judicom's")
    except RuntimeError as exc:
        log("photos not updated: %s (keeping the photos that are here)" % exc)
        return 1
    if dry_run:
        new = sorted(set(remote) - set(os.listdir(local_folder) if os.path.isdir(local_folder) else []))
        log("would copy %d new file(s)%s and remove %d%s; %d picture(s) on the NAS"
            % (len(new), ": " + ", ".join(new) if new else "", len(to_remove), ": " + ", ".join(to_remove) if to_remove else "",
               len(remote_pictures)))
        return 0
    try:
        changes = copier(local_folder)
    except RuntimeError as exc:
        log("photos not updated: %s" % exc)
        return 1
    def name(change):                                   # ">f+++++++++ Waylyn 1.jpg" / "*deleting   old.jpg" -> the file name
        return change.split(None, 1)[1] if len(change.split(None, 1)) > 1 else ""
    added = [name(c) for c in changes if c.startswith(">f") and "+++++++" in c.split(None, 1)[0]]
    changed = [name(c) for c in changes if c.startswith(">f") and "+++++++" not in c.split(None, 1)[0]]
    removed = [name(c) for c in changes if c.startswith("*deleting")]
    if added or changed or removed:
        log("photos updated: %d new, %d changed, %d removed (%s); %d picture(s) now"
            % (len(added), len(changed), len(removed), ", ".join(added + changed + removed), len(remote_pictures)))
    else:
        log("photos unchanged: %d picture(s)" % len(remote_pictures))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m judicom.photo_sync", description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="say what would be copied and removed; change nothing")
    ap.add_argument("--force", action="store_true", help="allow removing more than half of the pictures (never all of them)")
    args = ap.parse_args(argv)
    sys.exit(sync(dry_run=args.dry_run, force=args.force))


if __name__ == "__main__":
    main()
