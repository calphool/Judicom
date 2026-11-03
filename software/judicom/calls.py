"""The phone software: baresip, driven through its ctrl_tcp module (a local TCP socket carrying JSON in netstrings).

    calls = Baresip(log=log)            # connects to 127.0.0.1:4444 (config.BARESIP_CTRL); reconnects by itself
    calls.do(("dial", party))           # the machine's actions: ("dial", Party) ("answer",) ("hangup",) ("reject",)
    events = calls.poll()               # call often: what baresip reported, as machine events:
                                        #   ("incoming", "sip:+13125550187@...")   ("answered",)   ("remote_ended",)   ("call_failed",)

    python3 -m judicom.calls                  print everything baresip reports (start baresip first, in another terminal)
    python3 -m judicom.calls --dial 100       make a call and print what happens; Ctrl-C hangs up

Which baresip events become which machine events:
  CALL_INCOMING     -> ("incoming", the caller's SIP address)     the machine decides: ring, or reject (busy)
  CALL_ESTABLISHED  -> ("answered",) for our own outgoing call (an incoming one was answered by us: nothing to report)
  CALL_CLOSED       -> ("remote_ended",): they hung up, declined, the number did not exist, ...  (the machine knows what it means
                       in each mode: "No answer." while calling, "Call just ended" during a call, back to the photos while ringing)
Only the call we are on counts: events for any other call (an old one closing late, say) are ignored.
If baresip is not running, a dial fails at once ("No answer.") instead of waiting for the ring-out time.

baresip's config must have:  module_app ctrl_tcp.so   ctrl_tcp_listen 127.0.0.1:4444   call_max_calls 1
(call_max_calls 1: baresip itself answers a second caller with "busy" while a call is on).
"""
import json
import socket
import time

from . import config

RECONNECT_SECONDS = 5.0


# ------------------------------------------------------------------ netstrings ------------------------------------------------
def netstring(payload):
    """b'{"a":1}' -> b'7:{"a":1},'"""
    return b"%d:%s," % (len(payload), payload)


class NetstringReader:
    """Collects bytes from the socket and hands out the complete netstrings in them."""

    MAX = 1 << 20

    def __init__(self):
        self.buf = b""

    def feed(self, data):
        self.buf += data
        out = []
        while True:
            colon = self.buf.find(b":")
            if colon < 0:
                if len(self.buf) > 12:                      # no length prefix where one should be: out of step, start over
                    raise ValueError("bad netstring prefix %r" % self.buf[:12])
                return out
            head = self.buf[:colon]
            if not head.isdigit() or int(head) > self.MAX:
                raise ValueError("bad netstring length %r" % head[:12])
            n = int(head)
            end = colon + 1 + n
            if len(self.buf) < end + 1:
                return out                                  # not all here yet
            if self.buf[end:end + 1] != b",":
                raise ValueError("netstring not closed with a comma")
            out.append(self.buf[colon + 1:end])
            self.buf = self.buf[end + 1:]


# ------------------------------------------------------------------ baresip -----------------------------------------------
class Baresip:
    def __init__(self, address=None, log=None, connect=socket.create_connection, clock=time.monotonic):
        self.address = tuple(config.BARESIP_CTRL if address is None else address)
        self.log = log or (lambda msg: None)
        self._connect, self.clock = connect, clock
        self.sock = None
        self._reader = NetstringReader()
        self._retry_at = 0.0
        self._token = 0
        self._pending = {}              # token -> command, until baresip answers
        self._events = []               # machine events waiting for poll()
        self.call_id = None             # the call we are on ("" until baresip has told us its id)
        self._said_down = False
        self.registered = None          # True / False once baresip has said; None: not known

    # ---- connection
    @property
    def connected(self):
        return self.sock is not None

    def _ensure(self):
        if self.sock is not None:
            return True
        now = self.clock()
        if now < self._retry_at:
            return False
        self._retry_at = now + RECONNECT_SECONDS
        try:
            sock = self._connect(self.address, 1.0)
            sock.setblocking(False)
        except OSError as exc:
            if not self._said_down:
                self.log("baresip is not reachable at %s:%d (%s); trying again every %g s"
                         % (self.address[0], self.address[1], exc, RECONNECT_SECONDS))
                self._said_down = True
            return False
        self.sock, self._reader = sock, NetstringReader()
        self._said_down = False
        self.log("connected to baresip at %s:%d" % self.address)
        return True

    def _drop(self, why):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None
        self._pending.clear()
        self._retry_at = self.clock() + RECONNECT_SECONDS
        self.log("lost baresip (%s)" % why)
        if self.call_id is not None:                        # whatever call there was is gone with it
            self.call_id = None
            self._events.append(("remote_ended",))

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    # ---- the machine's actions
    def do(self, action):
        what = action[0]
        if what == "dial":
            party = action[1]
            if not self._send("dial", party.dial):
                self.log("      cannot call %s: baresip is not running" % party.label)
                self._events.append(("call_failed",))       # "No answer." at once, not after the ring-out time
                return
            self.call_id = ""                               # ours, id not known yet: the next outgoing call event tells it
        elif what == "answer":
            self._send("accept")
        elif what in ("hangup", "reject"):
            self._send("hangup")
            self.call_id = None                             # whatever baresip says about that call from now on is old news
        else:
            raise ValueError("unknown action %r" % (action,))

    def _send(self, command, params=None):
        if not self._ensure():
            return False
        self._token += 1
        token = str(self._token)
        msg = {"command": command, "token": token}
        if params is not None:
            msg["params"] = params
        try:
            self.sock.sendall(netstring(json.dumps(msg).encode()))
        except OSError as exc:
            self._drop(exc)
            return False
        self._pending[token] = command
        self.log("      baresip <- %s%s" % (command, " " + params if params else ""))
        return True

    # ---- what baresip says
    def poll(self):
        """Machine events since the last call."""
        if self._ensure():
            while True:
                try:
                    data = self.sock.recv(65536)
                except BlockingIOError:
                    break
                except OSError as exc:
                    self._drop(exc)
                    break
                if not data:
                    self._drop("baresip closed the connection")
                    break
                try:
                    messages = self._reader.feed(data)
                except ValueError as exc:
                    self._drop(exc)
                    break
                for raw in messages:
                    self._message(raw)
        events, self._events = self._events, []
        return events

    def _message(self, raw):
        try:
            msg = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            self.log("      (baresip sent something that is not JSON: %r)" % raw[:80])
            return
        if msg.get("response"):
            self._response(msg)
        elif msg.get("event"):
            self._event(msg)

    def _response(self, msg):
        command = self._pending.pop(str(msg.get("token")), None)
        if msg.get("ok") is False:
            self.log("      baresip could not %s: %s" % (command or "do that", str(msg.get("data", "")).strip()))
            if command == "dial" and self.call_id == "":
                self.call_id = None
                self._events.append(("call_failed",))

    def _event(self, msg):
        kind = str(msg.get("type", ""))
        cid = msg.get("id")
        cid = None if cid is None else str(cid)
        if kind.startswith("REGISTER_"):
            ok = kind == "REGISTER_OK"
            if ok != self.registered:
                self.registered = ok
                self.log("baresip %s with the PBX%s" % ("registered" if ok else "is NOT registered",
                                                        "" if ok else ": " + str(msg.get("param", ""))))
            return
        if not kind.startswith("CALL_"):
            return
        direction = msg.get("direction")
        if kind == "CALL_INCOMING":
            if self.call_id is not None:
                self.log("      (ignored a second incoming call while one is on: set call_max_calls 1 in ~/.baresip/config "
                         "so that baresip answers it with busy)")
                return
            self.call_id = cid if cid is not None else ""
            self._events.append(("incoming", str(msg.get("peeruri", ""))))
            return
        if self.call_id is None:
            return                                          # no call of ours: an old one finishing late
        if self.call_id == "":
            if cid is not None and direction == "outgoing":
                self.call_id = cid                          # the call we just dialled has told us its id
        elif cid is not None and cid != self.call_id:
            return                                          # some other call
        if kind == "CALL_ESTABLISHED":
            if direction != "incoming":
                self._events.append(("answered",))
        elif kind == "CALL_CLOSED":
            self.log("      call closed: %s" % (str(msg.get("param", "")).strip() or "no reason given"))
            self.call_id = None
            self._events.append(("remote_ended",))


class NoCalls:
    """Stands in for baresip (--no-calls, or a PC): says what it would have done.  The keys y / f / e / i / u pretend."""

    def __init__(self, log):
        self.log = log

    def do(self, action):
        what = " ".join(getattr(a, "label", a) for a in action)
        self.log("      (no phone software: would %s)" % what)

    def poll(self):
        return []

    def close(self):
        pass


# ------------------------------------------------------------------ try it by hand -------------------------------------------
def main(argv=None):
    import argparse
    from .machine import Party
    ap = argparse.ArgumentParser(prog="python3 -m judicom.calls",
                                 description="Talk to baresip: print what it reports; with --dial, make a call (Ctrl-C hangs up).")
    ap.add_argument("--dial", metavar="NUMBER", help="call this number or extension (e.g. 100: the melody test on the PBX)")
    ap.add_argument("--answer", action="store_true", help="answer the next incoming call by itself")
    ap.add_argument("--port", type=int, default=config.BARESIP_CTRL[1])
    args = ap.parse_args(argv)
    start = time.monotonic()
    log = lambda msg: print("[%6.1f s] %s" % (time.monotonic() - start, msg), flush=True)      # noqa: E731
    calls = Baresip((config.BARESIP_CTRL[0], args.port), log)
    raw_message = calls._message

    def show_raw(raw):                                       # print every message exactly as baresip sent it
        log("   raw: %s" % raw.decode("utf-8", "replace"))
        raw_message(raw)
    calls._message = show_raw
    if not calls._ensure():
        raise SystemExit("baresip is not running (start it in another terminal: baresip)")
    if args.dial:
        calls.do(("dial", Party(dial=args.dial)))
    try:
        while True:
            for event in calls.poll():
                log("-> machine event: %s" % " ".join(event))
                if event[0] == "incoming" and args.answer:
                    calls.do(("answer",))
                if event[0] in ("remote_ended", "call_failed") and args.dial:
                    return
            time.sleep(0.05)
    except KeyboardInterrupt:
        if calls.call_id is not None:
            calls.do(("hangup",))
            time.sleep(0.5)
            for _ in calls.poll():
                pass
    finally:
        calls.close()


if __name__ == "__main__":
    main()
