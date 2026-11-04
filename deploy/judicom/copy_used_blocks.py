#!/usr/bin/env python3
"""Writes an ext4 partition to standard output with only its used blocks copied and its free blocks as zeros: the same image
`e2image -ra` makes, but without e2image's mount check (which creates /.ismount-test-file and so waits forever on a frozen root
partition).  Run by backup_stream.sh as root, while the partition is frozen.

    copy_used_blocks.py DEVICE [SIZE_BYTES]

Which blocks are free comes from `dumpe2fs` (read-only).  The output is SIZE_BYTES long (default: the size of DEVICE), so it
also covers any space after the end of the file system (as zeros).  Reads go past the memory cache (it is dropped first), so
nothing stale from earlier reads ends up in the image.  Only the standard library.
"""
import os
import re
import subprocess
import sys

CHUNK = 4 * 1024 * 1024
DUMPE2FS = os.environ.get("DUMPE2FS", "/usr/sbin/dumpe2fs")


def free_ranges(dumpe2fs_text):
    """(block size, block count, [(first, last) free block ranges, inclusive]) from dumpe2fs's output."""
    size = int(re.search(r"^Block size:\s+(\d+)", dumpe2fs_text, re.M).group(1))
    count = int(re.search(r"^Block count:\s+(\d+)", dumpe2fs_text, re.M).group(1))
    free = []
    for line in re.findall(r"^\s+Free blocks:(.*)$", dumpe2fs_text, re.M):    # the indented per-group lines only
        for part in line.split(","):
            part = part.strip()
            if not part:
                continue
            a, _, b = part.partition("-")
            free.append((int(a), int(b or a)))
    free.sort()
    return size, count, free


def used_ranges(count, free):
    """The complement of the free ranges within [0, count): [(first, last)] used, inclusive."""
    used, next_block = [], 0
    for a, b in free:
        if a > next_block:
            used.append((next_block, a - 1))
        next_block = max(next_block, b + 1)
    if next_block < count:
        used.append((next_block, count - 1))
    return used


def device_size(fd):
    return os.lseek(fd, 0, os.SEEK_END)


def write_zeros(out, n, zeros):
    while n > 0:
        k = min(n, len(zeros))
        out.write(zeros[:k])
        n -= k


def copy(device, out, size_bytes=None, dumpe2fs_text=None):
    if dumpe2fs_text is None:
        dumpe2fs_text = subprocess.run([DUMPE2FS, device], capture_output=True, text=True, check=True).stdout
    block, count, free = free_ranges(dumpe2fs_text)
    fd = os.open(device, os.O_RDONLY)
    try:
        total = device_size(fd) if size_bytes is None else size_bytes
        try:
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)        # forget cached copies: read what is on the card now
        except OSError:
            pass
        zeros = bytes(CHUNK)
        pos = 0
        for first, last in used_ranges(count, free):
            start, end = first * block, (last + 1) * block
            write_zeros(out, start - pos, zeros)
            pos = start
            while pos < end:
                data = os.pread(fd, min(CHUNK, end - pos), pos)
                if not data:
                    raise OSError("short read at byte %d of %s" % (pos, device))
                out.write(data)
                pos += len(data)
        write_zeros(out, total - pos, zeros)                         # free blocks at the end, and space after the file system
    finally:
        os.close(fd)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if not 1 <= len(args) <= 2:
        sys.exit(__doc__)
    out = sys.stdout.buffer
    try:
        copy(args[0], out, int(args[1]) if len(args) > 1 else None)
        out.flush()
    except BrokenPipeError:
        sys.exit(141)


if __name__ == "__main__":
    main()
