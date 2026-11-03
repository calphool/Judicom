"""Tests for judicom/calls.py: the test plays baresip at the other end of a socket pair.   Run from the software folder:
python3 -m unittest -v"""
import json
import socket
import unittest

from judicom.calls import RECONNECT_SECONDS, Baresip, NetstringReader, netstring
from judicom.machine import Party

ANN = Party("Ann", "daughter", "3125550187", "3125550187")


class Netstrings(unittest.TestCase):
    def test_round_trip(self):
        self.assertEqual(netstring(b'{"a":1}'), b'7:{"a":1},')
        self.assertEqual(NetstringReader().feed(b'7:{"a":1},2:{},'), [b'{"a":1}', b"{}"])

    def test_in_pieces(self):
        r = NetstringReader()
        self.assertEqual(r.feed(b"7:"), [])
        self.assertEqual(r.feed(b'{"a"'), [])
        self.assertEqual(r.feed(b":1},3"), [b'{"a":1}'])
        self.assertEqual(r.feed(b":abc,"), [b"abc"])

    def test_garbage(self):
        for bad in (b"x:abc,", b"3:abcd", b"no colon at all here"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    NetstringReader().feed(bad)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class Base(unittest.TestCase):
    def setUp(self):
        self.clock, self.logged = Clock(), []
        self.up = True
        self.sockets = []
        self.calls = Baresip(("127.0.0.1", 4444), self.logged.append, connect=self.connect, clock=self.clock)

    def tearDown(self):
        self.calls.close()
        for s in self.sockets:
            s.close()

    def connect(self, address, timeout):
        if not self.up:
            raise ConnectionRefusedError(111, "Connection refused")
        ours, theirs = socket.socketpair()
        theirs.settimeout(1.0)
        self.baresip = theirs
        self.sockets += [ours, theirs]
        return ours

    def say(self, **msg):
        """baresip sends a message."""
        self.baresip.sendall(netstring(json.dumps(msg).encode()))

    def event(self, kind, **fields):
        self.say(event=True, type=kind, **fields)

    def heard(self):
        """The commands baresip received."""
        self.baresip.settimeout(0.2)
        data = b""
        try:
            while True:
                chunk = self.baresip.recv(65536)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            pass
        return [json.loads(m) for m in NetstringReader().feed(data)]

    def poll(self):
        return self.calls.poll()


class Outgoing(Base):
    def test_dial_answered_then_they_hang_up(self):
        self.calls.do(("dial", ANN))
        [cmd] = self.heard()
        self.assertEqual((cmd["command"], cmd["params"]), ("dial", "3125550187"))
        self.say(response=True, ok=True, data="", token=cmd["token"])
        self.event("CALL_RINGING", direction="outgoing", id="c1", peeruri="sip:3125550187@pbx")
        self.assertEqual(self.poll(), [])
        self.event("CALL_ESTABLISHED", direction="outgoing", id="c1")
        self.assertEqual(self.poll(), [("answered",)])
        self.event("CALL_CLOSED", direction="outgoing", id="c1", param="Connection reset by peer")
        self.assertEqual(self.poll(), [("remote_ended",)])
        self.assertIsNone(self.calls.call_id)

    def test_number_that_does_not_exist(self):
        self.calls.do(("dial", ANN))
        self.event("CALL_CLOSED", direction="outgoing", id="c1", param="404 Not Found")
        self.assertEqual(self.poll(), [("remote_ended",)])          # the machine: CALLING + remote_ended = "No answer."
        self.assertIn("404 Not Found", self.logged[-1])

    def test_dial_refused_by_baresip(self):
        self.calls.do(("dial", ANN))
        [cmd] = self.heard()
        self.say(response=True, ok=False, data="no account", token=cmd["token"])
        self.assertEqual(self.poll(), [("call_failed",)])

    def test_we_hang_up_and_the_late_close_is_ignored(self):
        self.calls.do(("dial", ANN))
        self.event("CALL_RINGING", direction="outgoing", id="c1")
        self.poll()
        self.calls.do(("hangup",))
        self.assertEqual([c["command"] for c in self.heard()], ["dial", "hangup"])
        self.event("CALL_CLOSED", direction="outgoing", id="c1")
        self.assertEqual(self.poll(), [])

    def test_an_old_call_closing_late_does_not_end_the_new_one(self):
        self.calls.do(("dial", ANN))
        self.event("CALL_RINGING", direction="outgoing", id="c1")
        self.poll()
        self.calls.do(("hangup",))
        self.calls.do(("dial", ANN))                                 # straight away the next call
        self.event("CALL_RINGING", direction="outgoing", id="c2")
        self.poll()
        self.event("CALL_CLOSED", direction="outgoing", id="c1")     # the first one's goodbye arrives late
        self.event("CALL_ESTABLISHED", direction="outgoing", id="c2")
        self.assertEqual(self.poll(), [("answered",)])

    def test_events_without_ids_still_work(self):
        self.calls.do(("dial", ANN))
        self.event("CALL_ESTABLISHED", direction="outgoing")
        self.event("CALL_CLOSED", direction="outgoing")
        self.assertEqual(self.poll(), [("answered",), ("remote_ended",)])


class Incoming(Base):
    def test_ring_answer_hang_up(self):
        self.poll()                                                  # connected
        self.event("CALL_INCOMING", direction="incoming", id="c9", peeruri="sip:+13125550187@100.64.0.1")
        self.assertEqual(self.poll(), [("incoming", "sip:+13125550187@100.64.0.1")])
        self.calls.do(("answer",))
        self.assertEqual([c["command"] for c in self.heard()], ["accept"])
        self.event("CALL_ESTABLISHED", direction="incoming", id="c9")
        self.assertEqual(self.poll(), [])                           # we answered it: the machine knows already
        self.event("CALL_CLOSED", direction="incoming", id="c9")
        self.assertEqual(self.poll(), [("remote_ended",)])

    def test_caller_gives_up(self):
        self.poll()
        self.event("CALL_INCOMING", direction="incoming", id="c9", peeruri="sip:101@pbx")
        self.event("CALL_CLOSED", direction="incoming", id="c9", param="Request terminated")
        self.assertEqual(self.poll(), [("incoming", "sip:101@pbx"), ("remote_ended",)])

    def test_reject(self):
        self.poll()
        self.event("CALL_INCOMING", direction="incoming", id="c9", peeruri="sip:101@pbx")
        self.poll()
        self.calls.do(("reject",))
        self.assertEqual([c["command"] for c in self.heard()], ["hangup"])
        self.event("CALL_CLOSED", direction="incoming", id="c9")
        self.assertEqual(self.poll(), [])

    def test_second_incoming_during_a_call_is_ignored(self):
        self.poll()
        self.event("CALL_INCOMING", direction="incoming", id="c9", peeruri="sip:101@pbx")
        self.event("CALL_INCOMING", direction="incoming", id="c10", peeruri="sip:102@pbx")
        self.event("CALL_CLOSED", direction="incoming", id="c10")
        self.assertEqual(self.poll(), [("incoming", "sip:101@pbx")])
        self.assertTrue(any("call_max_calls 1" in m for m in self.logged))


class Connection(Base):
    def test_not_running_dial_fails_at_once_and_says_so_once(self):
        self.up = False
        self.calls.do(("dial", ANN))
        self.assertEqual(self.poll(), [("call_failed",)])
        self.calls.poll()
        self.clock.t += RECONNECT_SECONDS + 1
        self.calls.poll()
        self.assertEqual(sum("not reachable" in m for m in self.logged), 1)

    def test_reconnects_when_baresip_comes_back(self):
        self.up = False
        self.poll()
        self.up = True
        self.clock.t += 1
        self.poll()
        self.assertFalse(self.calls.connected)                      # waits RECONNECT_SECONDS between tries
        self.clock.t += RECONNECT_SECONDS
        self.poll()
        self.assertTrue(self.calls.connected)

    def test_baresip_dies_during_a_call(self):
        self.calls.do(("dial", ANN))
        self.event("CALL_ESTABLISHED", direction="outgoing", id="c1")
        self.assertEqual(self.poll(), [("answered",)])
        self.baresip.close()
        self.assertEqual(self.poll(), [("remote_ended",)])
        self.assertFalse(self.calls.connected)

    def test_registration_is_reported_on_change(self):
        self.poll()
        self.event("REGISTER_OK", param="200 OK")
        self.event("REGISTER_OK", param="200 OK")
        self.event("REGISTER_FAIL", param="408 Request Timeout")
        self.assertEqual(self.poll(), [])
        self.assertEqual(sum("baresip registered with the PBX" in m for m in self.logged), 1)
        self.assertIn("NOT registered", self.logged[-1])
        self.assertIn("408", self.logged[-1])
        self.assertFalse(self.calls.registered)

    def test_not_json_is_skipped(self):
        self.poll()
        self.baresip.sendall(netstring(b"hello"))
        self.event("CALL_INCOMING", direction="incoming", id="c9", peeruri="sip:101@pbx")
        self.assertEqual(self.poll(), [("incoming", "sip:101@pbx")])

    def test_unknown_action(self):
        with self.assertRaises(ValueError):
            self.calls.do(("explode",))


if __name__ == "__main__":
    unittest.main()
