#!/usr/bin/env python3
"""Keeps the NAS ready for VoIP.ms changing its Chicago server's address.   (runs as root, hourly: voipms-address-check.timer)

Two places only let VoIP.ms in by its address:
  - the firewall: set "voipms" in table inet asterisk_test (/etc/asterisk-firewall.nft); SIP on eth0 from anyone else is dropped
  - Asterisk: "match=" in the voipms-identify section of voipms.conf
Every hour this looks up chicago4.voip.ms.  An address that is not in both yet is ADDED (never removed: VoIP.ms may answer from
the old and the new one for a while): to the live firewall set at once, to /etc/asterisk-firewall.nft (so it is there after a
reboot), and to the match= line, followed by a pjsip reload.  Nothing changes when the lookup fails or gives something strange
(a private address, too many addresses); a lookup that keeps failing writes a WARNING to the journal every hour:
    journalctl -u voipms-address-check

    voipms_address_check.py            check, and fix if needed
    voipms_address_check.py --dry-run  only say what it would do
Only the standard library.
"""
import argparse
import ipaddress
import os
import re
import socket
import subprocess
import sys
import tempfile

HOST = "chicago4.voip.ms"
NFT_FILE = "/etc/asterisk-firewall.nft"
PJSIP_FILE = "/home/pi/asterisk-test/config/voipms.conf"
NFT = "/usr/sbin/nft"
RELOAD = ["/usr/bin/docker", "exec", "asterisk-test", "asterisk", "-rx", "module reload res_pjsip.so"]
MAX_ADDRESSES = 6              # a lookup giving more than this is not believed
MAX_KEPT = 12                  # never more than this many addresses in the firewall set (the oldest added go first)

NFT_TEMPLATE = """# Written by voipms_address_check.py (from deploy/nas/firewall in the Judicom repository).  Loaded at boot by
# asterisk-firewall.service.  SIP (UDP 5060) on the home network (eth0) is dropped unless it comes from VoIP.ms; the addresses
# in the set are kept up to date by voipms-address-check.timer (it only ever adds).
# The first two lines make loading this file replace the table in one step, whether or not it is there yet.
table inet asterisk_test
delete table inet asterisk_test
table inet asterisk_test {
    set voipms {
        type ipv4_addr
        elements = { %s }
    }
    chain input {
        type filter hook input priority -10; policy accept;

        iifname "eth0" udp dport 5060 ip saddr != @voipms drop
    }
}
"""


def resolve(host=HOST):
    """The host's public IPv4 addresses, sorted; raises RuntimeError if there are none or they look wrong."""
    try:
        infos = socket.getaddrinfo(host, 5060, socket.AF_INET, socket.SOCK_DGRAM)
    except OSError as exc:
        raise RuntimeError("cannot look up %s: %s" % (host, exc)) from None
    addresses = sorted({info[4][0] for info in infos}, key=ipaddress.IPv4Address)
    if not addresses:
        raise RuntimeError("%s has no IPv4 address" % host)
    if len(addresses) > MAX_ADDRESSES:
        raise RuntimeError("%s gave %d addresses (more than %d): not believed" % (host, len(addresses), MAX_ADDRESSES))
    for a in addresses:
        ip = ipaddress.IPv4Address(a)
        if not ip.is_global:
            raise RuntimeError("%s gave %s, which is not a public address: not believed" % (host, a))
    return addresses


def file_addresses(nft_text):
    """The addresses in the set of an asterisk-firewall.nft file (or the single one of the old fixed rule)."""
    m = re.search(r"set\s+voipms\s*\{.*?elements\s*=\s*\{([^}]*)\}", nft_text, re.S)
    if m:
        return [a.strip() for a in m.group(1).split(",") if a.strip()]
    m = re.search(r"ip\s+saddr\s+!=\s+(\d+\.\d+\.\d+\.\d+)", nft_text)
    return [m.group(1)] if m else []


def nft_text(addresses):
    return NFT_TEMPLATE % ", ".join(addresses)


def match_addresses(pjsip_text):
    """(the addresses on voipms-identify's match= line, the line) or ([], None)."""
    section = re.search(r"^\[voipms-identify\][^\[]*", pjsip_text, re.M)
    if not section:
        return [], None
    m = re.search(r"^match\s*=\s*(.+)$", section.group(0), re.M)
    if not m:
        return [], None
    return [a.strip() for a in m.group(1).split(",") if a.strip()], m.group(0)


def with_match(pjsip_text, addresses):
    """pjsip_text with voipms-identify's match= line listing `addresses`."""
    _, line = match_addresses(pjsip_text)
    if line is None:
        raise RuntimeError("no match= line in [voipms-identify]")
    start = re.search(r"^\[voipms-identify\]", pjsip_text, re.M).start()
    head, tail = pjsip_text[:start], pjsip_text[start:]
    return head + tail.replace(line, "match=" + ",".join(addresses), 1)


def write_atomically(path, text):
    st = os.stat(path) if os.path.exists(path) else None
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".voipms-check.")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        if st is not None:
            os.chmod(tmp, st.st_mode & 0o7777)
            try:
                os.chown(tmp, st.st_uid, st.st_gid)          # keep the owner (pi for voipms.conf, root for the .nft file)
            except PermissionError:
                pass
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def check(resolver=resolve, nft_file=NFT_FILE, pjsip_file=PJSIP_FILE, run=subprocess.run, dry_run=False, log=print):
    """0: everything up to date (or brought up to date, or the lookup failed: nothing changed), 1: something could not be fixed."""
    try:
        found = resolver()
    except RuntimeError as exc:
        log("WARNING: %s; nothing changed (the addresses allowed now stay as they are)" % exc)
        return 0
    with open(nft_file) as fh:
        nft_now = fh.read()
    with open(pjsip_file) as fh:
        pjsip_now = fh.read()
    in_nft, in_match = file_addresses(nft_now), match_addresses(pjsip_now)[0]
    new_nft = [a for a in found if a not in in_nft]
    new_match = [a for a in found if a not in in_match]
    has_set = "set voipms" in nft_now
    if not new_nft and not new_match and has_set:
        log("VoIP.ms (%s) is %s: allowed in the firewall and known to Asterisk" % (HOST, ", ".join(found)))
        return 0
    keep_nft = (in_nft + new_nft)[-MAX_KEPT:]
    keep_match = (in_match + new_match)[-MAX_KEPT:]
    if dry_run:
        log("would allow %s in the firewall%s and %s in Asterisk"
            % (", ".join(keep_nft), "" if has_set else " (as a set, replacing the fixed rule)", ", ".join(keep_match)))
        return 0
    status = 0
    if new_nft or not has_set:
        write_atomically(nft_file, nft_text(keep_nft))
        r = run([NFT, "-f", nft_file], capture_output=True, text=True)
        if r.returncode != 0:
            log("ERROR: the firewall did not take the new addresses: %s" % (r.stderr or r.stdout).strip())
            status = 1
        else:
            log("firewall: VoIP.ms addresses now %s%s" % (", ".join(keep_nft), " (added %s)" % ", ".join(new_nft) if new_nft else ""))
    if new_match:
        write_atomically(pjsip_file, with_match(pjsip_now, keep_match))
        r = run(RELOAD, capture_output=True, text=True)
        if r.returncode != 0:
            log("ERROR: Asterisk did not reload: %s" % (r.stderr or r.stdout).strip())
            status = 1
        else:
            log("Asterisk: voipms-identify now matches %s (added %s)" % (", ".join(keep_match), ", ".join(new_match)))
    return status


def main(argv=None):
    ap = argparse.ArgumentParser(description="Keep the NAS's VoIP.ms address allowed in the firewall and in Asterisk.")
    ap.add_argument("--dry-run", action="store_true", help="only say what it would do")
    args = ap.parse_args(argv)
    sys.exit(check(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
