#!/usr/bin/env python3
"""Writes an ext4 partition to standard output with only its used blocks copied and its free blocks as zeros: the same image
`e2image -ra` makes, but without e2image's mount check (which creates /.ismount-test-file and so waits forever on a frozen root
partition).  Run by backup_stream.sh as root, while the partition is frozen.

    copy_used_blocks.py DEVICE [SIZE_BYTES]

Which blocks are free comes from `dumpe2fs` (read-only).  The partition is read in 4 MB windows (long sequential reads),
skipping windows with nothing in use, and the free blocks in each window are sent as zeros.  The output is SIZE_BYTES long (default: the size of DEVICE), so it
also covers any space after the end of the file system (as zeros).  Reads go past the memory cache (it is dropped first), so
nothing stale from earlier reads ends up in the image.  Only the standard library.

If COPY_POSITION names a file (it must be in memory: the partition is frozen), how far it has got and the whole size, in MB, are
kept in it, for the progress bar in backup_judicom.sh.  Not being able to write that file never stops the copy.
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


def position_keeper(path):
    """A function note(position, total) that keeps them in `path` (bytes in, MB in the file), or does nothing if it cannot."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644) if path else None
    except OSError:
        fd = None

    def note(position, total):
        if fd is not None:
            try:
                os.pwrite(fd, b"%-12d %-12d\n" % (position >> 20, total >> 20), 0)      # always the same length: nothing left over
            except OSError:
                pass
    return note


def copy(device, out, size_bytes=None, dumpe2fs_text=None, note=lambda position, total: None):
    """Go through the partition in CHUNK-sized windows: a window with no used block is sent as zeros without being read; any
    other window is read in one go (long, sequential reads: SD cards are slow at many small ones) and its free blocks are set to
    zeros before it is sent.  The output is the same as copying only the used blocks."""
    if dumpe2fs_text is None:
        dumpe2fs_text = subprocess.run([DUMPE2FS, device], capture_output=True, text=True, check=True).stdout
    block, count, free = free_ranges(dumpe2fs_text)
    used = [(a * block, (b + 1) * block) for a, b in used_ranges(count, free)]          # byte ranges [start, end)
    fd = os.open(device, os.O_RDONLY)
    try:
        total = device_size(fd) if size_bytes is None else size_bytes
        try:
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)        # forget cached copies: read what is on the card now
        except OSError:
            pass
        zeros = bytes(CHUNK)
        i = 0                                                         # the first used range that may still matter
        for pos in range(0, total, CHUNK):
            note(pos, total)
            end = min(pos + CHUNK, total)
            while i < len(used) and used[i][1] <= pos:
                i += 1
            if i >= len(used) or used[i][0] >= end:
                out.write(zeros[:end - pos])                          # nothing used in this window
                continue
            data = bytearray(os.pread(fd, end - pos, pos))
            if len(data) != end - pos:
                raise OSError("short read at byte %d of %s" % (pos, device))
            cursor, j = pos, i                                        # blank the free parts of the window
            while j < len(used) and used[j][0] < end:
                start = max(used[j][0], pos)
                if start > cursor:
                    data[cursor - pos:start - pos] = zeros[:start - cursor]
                cursor = max(cursor, min(used[j][1], end))
                j += 1
            if cursor < end:
                data[cursor - pos:] = zeros[:end - cursor]
            out.write(data)
        note(total, total)
    finally:
        os.close(fd)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if not 1 <= len(args) <= 2:
        sys.exit(__doc__)
    out = sys.stdout.buffer
    try:
        copy(args[0], out, int(args[1]) if len(args) > 1 else None, note=position_keeper(os.environ.get("COPY_POSITION")))
        out.flush()
    except BrokenPipeError:
        sys.exit(141)


if __name__ == "__main__":
    main()
