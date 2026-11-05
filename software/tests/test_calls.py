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


# Recorded from baresip 1.1.0 on the Judicom (2026-11-04): python3 -m judicom.calls --dial 100, and --answer with an originate.
REAL_DIAL_100 = [
    '{"event":true,"type":"CALL_LOCAL_SDP","class":"other","accountaor":"sip:judicom@100.64.0.1:5060","direction":"outgoing",'
    '"peeruri":"sip:100@100.64.0.1;transport=udp","remoteaudiodir":"sendrecv","param":"offer"}',
    '{"response":true,"ok":true,"data":"call id: 0f5f9210ca63c157\\n","token":"1"}',
    '{"event":true,"type":"CALL_ANSWERED","class":"call","accountaor":"sip:judicom@100.64.0.1:5060","direction":"outgoing",'
    '"peeruri":"sip:100@100.64.0.1;transport=udp","id":"0f5f9210ca63c157","remoteaudiodir":"sendrecv",'
    '"param":"sip:100@100.64.0.1;transport=udp"}',
    '{"event":true,"type":"CALL_REMOTE_SDP","class":"other","accountaor":"sip:judicom@100.64.0.1:5060","direction":"outgoing",'
    '"peeruri":"sip:100@100.64.0.1;transport=udp","id":"0f5f9210ca63c157","remoteaudiodir":"sendrecv","param":"answer"}',
    '{"event":true,"type":"CALL_ESTABLISHED","class":"call","accountaor":"sip:judicom@100.64.0.1:5060","direction":"outgoing",'
    '"peeruri":"sip:100@100.64.0.1;transport=udp","id":"0f5f9210ca63c157","remoteaudiodir":"sendrecv",'
    '"param":"sip:100@100.64.0.1;transport=udp"}',
    '{"event":true,"type":"CALL_RTPESTAB","class":"other","accountaor":"sip:judicom@100.64.0.1:5060","direction":"outgoing",'
    '"peeruri":"sip:100@100.64.0.1;transport=udp","id":"0f5f9210ca63c157","remoteaudiodir":"sendrecv","param":"audio"}',
    '{"event":true,"type":"CALL_RTCP","class":"call","accountaor":"sip:judicom@100.64.0.1:5060","direction":"outgoing",'
    '"peeruri":"sip:100@100.64.0.1;transport=udp","id":"0f5f9210ca63c157","remoteaudiodir":"sendrecv","param":"audio",'
    '"rtcp_stats":{"tx":{"sent":251,"lost":0,"jit":125},"rx":{"sent":250,"lost":0,"jit":125},"rtt":3647}}',
    '{"event":true,"type":"CALL_CLOSED","class":"call","accountaor":"sip:judicom@100.64.0.1:5060","direction":"outgoing",'
    '"peeruri":"sip:100@100.64.0.1;transport=udp","id":"0f5f9210ca63c157","remoteaudiodir":"sendrecv",'
    '"param":"Connection reset by peer"}',
]
_IN = ('"accountaor":"sip:judicom@100.64.0.1:5060","direction":"incoming","peeruri":"sip:anonymous@anonymous.invalid",'
       '"peerdisplayname":"Anonymous","id":"a4317d9d-c346-49b0-a431-35d22ab6125f","remoteaudiodir":"sendrecv"')
REAL_INCOMING = [
    '{"event":true,"type":"REGISTER_OK","class":"register","accountaor":"sip:judicom@100.64.0.1:5060","param":"200 OK"}',
    '{"event":true,"type":"CALL_INCOMING","class":"call",' + _IN + ',"param":"sip:anonymous@anonymous.invalid"}',
    "ANSWER",
    '{"event":true,"type":"CALL_REMOTE_SDP","class":"other",' + _IN + ',"param":"offer"}',
    '{"event":true,"type":"CALL_LOCAL_SDP","class":"other",' + _IN + ',"param":"answer"}',
    '{"response":true,"ok":true,"data":"","token":"1"}',
    '{"event":true,"type":"CALL_ESTABLISHED","class":"call",' + _IN + ',"param":"sip:anonymous@anonymous.invalid"}',
    '{"event":true,"type":"CALL_RTPESTAB","class":"other",' + _IN + ',"param":"audio"}',
    '{"event":true,"type":"CALL_CLOSED","class":"call",' + _IN + ',"param":"Connection reset by peer"}',
]


class RealBaresip(Base):
    """The exact messages baresip 1.1.0 sent on the Judicom."""

    def play(self, messages):
        events = []
        for m in messages:
            if m == "ANSWER":
                events += self.poll()
                self.calls.do(("answer",))
                continue
            self.baresip.sendall(netstring(m.encode()))
            events += self.poll()
        return events

    def test_dial_100(self):
        self.calls.do(("dial", Party(dial="100")))
        self.assertEqual(self.play(REAL_DIAL_100), [("answered",), ("remote_ended",)])
        self.assertIsNone(self.calls.call_id)

    def test_incoming_from_an_originate(self):
        self.poll()
        self.assertEqual(self.play(REAL_INCOMING), [("incoming", "sip:anonymous@anonymous.invalid"), ("remote_ended",)])
        self.assertTrue(self.calls.registered)

    def test_the_anonymous_caller_shows_as_unknown(self):
        from judicom.contacts import Contacts
        party = Contacts("/nonexistent").lookup("sip:anonymous@anonymous.invalid")
        self.assertEqual((party.name, party.dial), ("", ""))             # "Incoming call from unknown caller"


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

    def test_ready_only_when_connected_and_not_refused_by_the_pbx(self):
        self.up = False
        self.poll()
        self.assertFalse(self.calls.ready)                          # baresip not running
        self.up = True
        self.clock.t += RECONNECT_SECONDS + 1
        self.poll()
        self.assertTrue(self.calls.ready)                           # connected; registration not known yet: try
        self.event("REGISTER_FAIL", param="408 Request Timeout")
        self.poll()
        self.assertFalse(self.calls.ready)                          # no network / NAS down
        self.event("REGISTER_OK", param="200 OK")
        self.poll()
        self.assertTrue(self.calls.ready)

    def test_a_restarted_baresip_starts_unknown(self):
        self.poll()
        self.event("REGISTER_FAIL", param="408 Request Timeout")
        self.poll()
        self.baresip.close()
        self.poll()
        self.assertIsNone(self.calls.registered)

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
