"""Tests for deploy/nas/judicom/watch_judicom.py (the NAS's offline alert).  Nothing is sent: the mailer is a stand-in.
Run from the software folder:   python3 -m unittest -v"""
import datetime
import importlib.util
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "nas" / "judicom" / "watch_judicom.py"
spec = importlib.util.spec_from_file_location("watch_judicom", SCRIPT)
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)

UP = ("up", "")
DOWN = ("down", "the Judicom is not connected to the phone system")
START = datetime.datetime(2026, 11, 3, 14, 0).timestamp()        # Tuesday 2:00 PM


class Watching(unittest.TestCase):
    def setUp(self):
        self.sent, self.logged, self.broken = [], [], False
        self.settings = {"ALERT_TO": "joe@example.com", "DELAY_MINUTES": "30", "REMINDER_HOUR": "9"}
        self.state, self.now = {}, START

    def mailer(self, subject, body):
        if self.broken:
            raise OSError("Network is unreachable")
        self.sent.append((subject, body))

    def every_5_minutes(self, minutes, seen):
        for _ in range(int(minutes / 5)):
            self.now += 300
            self.state = watch.step(self.now, seen, self.state, self.settings, self.mailer, self.logged.append)

    def subjects(self):
        return [s for s, _ in self.sent]

    def test_all_well_sends_nothing(self):
        self.every_5_minutes(24 * 60, UP)
        self.assertEqual(self.sent, [])

    def test_a_short_blip_sends_nothing(self):
        self.every_5_minutes(60, UP)
        self.every_5_minutes(20, DOWN)
        self.every_5_minutes(60, UP)
        self.assertEqual(self.sent, [])
        self.assertTrue(any("no email" in m for m in self.logged))

    def test_one_email_after_30_minutes_then_one_when_back(self):
        self.every_5_minutes(10, UP)
        self.every_5_minutes(25, DOWN)
        self.assertEqual(self.sent, [])
        self.every_5_minutes(10, DOWN)
        self.assertEqual(len(self.sent), 1)
        self.assertTrue(self.subjects()[0].startswith("Judicom offline since Tuesday, November 3 at 2:"))
        self.every_5_minutes(4 * 60, DOWN)                       # hours more: nothing more today
        self.assertEqual(len(self.sent), 1)
        self.every_5_minutes(5, UP)
        self.assertEqual(self.subjects()[-1], "Judicom back online")
        self.assertIn("down for 4 hours", self.sent[-1][1])
        self.every_5_minutes(60, UP)
        self.assertEqual(len(self.sent), 2)

    def test_two_weeks_offline_is_one_email_a_day(self):
        self.every_5_minutes(10, UP)
        self.every_5_minutes(14 * 24 * 60, DOWN)
        self.assertEqual(len(self.sent), 1 + 14)                  # the first one, then one each morning
        reminders = [s for s in self.subjects() if s.startswith("Judicom still offline")]
        self.assertEqual(len(reminders), 14)
        self.assertIn("(13 days 18 hours", reminders[-1])
        for subject, body in self.sent[1:]:
            self.assertIn("Reason seen", body)

    def test_no_reminders_if_turned_off(self):
        self.settings["REMINDER_HOUR"] = ""
        self.every_5_minutes(3 * 24 * 60, DOWN)
        self.assertEqual(len(self.sent), 1)

    def test_morning_outage_gets_no_reminder_an_hour_later(self):
        self.now = datetime.datetime(2026, 11, 4, 7, 20).timestamp()
        self.every_5_minutes(3 * 60, DOWN)                         # first email ~7:50, 9:00 comes: no reminder yet
        self.assertEqual(len(self.sent), 1)

    def test_a_failed_send_is_tried_again(self):
        self.broken = True
        self.every_5_minutes(45, DOWN)
        self.assertEqual(self.sent, [])
        self.broken = False
        self.every_5_minutes(5, DOWN)
        self.assertEqual(len(self.sent), 1)
        self.broken = True
        self.every_5_minutes(10, UP)                               # "back" cannot go out yet ...
        self.broken = False
        self.every_5_minutes(5, UP)
        self.assertEqual(self.subjects()[-1], "Judicom back online")   # ... and is not lost

    def test_settings_delay(self):
        self.settings["DELAY_MINUTES"] = "10"
        self.every_5_minutes(15, DOWN)
        self.assertEqual(len(self.sent), 1)


REGISTERED = (" <Registration/ServerURI...>  <Auth...>  <Status.......>\n"
              "==========================================\n\n"
              " voipms-registration/sip:chicago4.voip.ms                voipms-auth                 Registered        (exp. 84s)\n\n"
              "Objects found: 1\n")


class Looking(unittest.TestCase):
    def run_with(self, out, code=0, exc=None, registrations=REGISTERED):
        def run(cmd, **kw):
            if exc:
                raise exc
            if cmd[-1] == "pjsip show registrations":
                return subprocess.CompletedProcess(cmd, 0, registrations, "")
            return subprocess.CompletedProcess(cmd, code, out, "")
        return watch.look(run)

    JUDICOM = "  Contact:  judicom/sip:judicom-0x18fb788@100.64.0.2:5 4bf24453a9 NonQual         nan\n"

    def test_line_to_voipms_down(self):
        for status in ("Unregistered", "Rejected", "Failed"):
            seen = self.run_with(self.JUDICOM, registrations=REGISTERED.replace("Registered   ", status + " "))
            self.assertEqual(seen, ("down", watch.NO_LINE), status)
        self.assertEqual(self.run_with(self.JUDICOM, registrations="\nObjects found: 0\n"), ("down", watch.NO_LINE))

    def test_both_down_names_both(self):
        seen = self.run_with("", registrations=REGISTERED.replace("Registered", "Rejected"))
        self.assertEqual(seen, ("down", watch.NO_JUDICOM + "; " + watch.NO_LINE))

    def test_registered(self):
        out = ("  Contact:  judicom/sip:judicom-0x18fb788@100.64.0.2:5 4bf24453a9 NonQual         nan\n"
               "  Contact:  voipms/sip:chicago4.voip.ms:5060               1d36b1265d Avail        22.239\n")
        self.assertEqual(self.run_with(out), ("up", ""))

    def test_not_registered(self):
        self.assertEqual(self.run_with("  Contact:  voipms/sip:chicago4.voip.ms:5060  1d36 Avail 22.2\n")[0], "down")
        self.assertEqual(self.run_with("  Contact:  judicom/sip:judicom@100.64.0.2 4bf2 Unavail nan\n")[0], "down")

    def test_asterisk_not_answering(self):
        self.assertIn("did not answer", self.run_with("Unable to connect to remote asterisk")[1])
        self.assertIn("did not answer", self.run_with("", code=1)[1])
        self.assertIn("did not answer", self.run_with("", exc=subprocess.TimeoutExpired("docker", 30))[1])


class Emails(unittest.TestCase):
    def test_line_down_has_its_own_subject_and_advice(self):
        subject, body = watch.message("offline", START, START + 3600, watch.NO_LINE)
        self.assertTrue(subject.startswith("Judi's phone line down since"))
        self.assertIn("pjsip show registrations", body)
        self.assertNotIn("nursing home", body)

    def test_judicom_offline_advice(self):
        subject, body = watch.message("offline", START, START + 3600, watch.NO_JUDICOM)
        self.assertTrue(subject.startswith("Judicom offline since"))
        self.assertIn("nursing home", body)
        self.assertNotIn("pjsip show registrations", body)
        both = watch.message("offline", START, START + 3600, watch.NO_JUDICOM + "; " + watch.NO_LINE)
        self.assertIn("nursing home", both[1])
        self.assertIn("pjsip show registrations", both[1])


class Pinging(unittest.TestCase):
    class Answer:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return b"OK"

    def test_ping_and_one_log_line_per_failure(self):
        logged, urls, broken = [], [], [False]

        def opener(req, timeout):
            urls.append(req.full_url)
            if broken[0]:
                raise OSError("Network is unreachable")
            return self.Answer()
        state = watch.ping("https://hc-ping.com/abc", {}, logged.append, opener)
        self.assertEqual((urls, state["ping_ok"], logged), (["https://hc-ping.com/abc"], True, []))
        broken[0] = True
        for _ in range(5):
            state = watch.ping("https://hc-ping.com/abc", state, logged.append, opener)
        self.assertFalse(state["ping_ok"])
        self.assertEqual(len(logged), 1)
        self.assertNotIn("hc-ping", logged[0])               # the private URL stays out of the log
        broken[0] = False
        state = watch.ping("https://hc-ping.com/abc", state, logged.append, opener)
        self.assertEqual((state["ping_ok"], logged[-1]), (True, "PING_URL works again"))


class Words(unittest.TestCase):
    def test_how_long(self):
        self.assertEqual(watch.how_long(45 * 60), "45 minutes")
        self.assertEqual(watch.how_long(3 * 3600 + 120), "3 hours 2 minutes")
        self.assertEqual(watch.how_long(2 * 86400 + 4 * 3600), "2 days 4 hours")
        self.assertEqual(watch.how_long(86400), "1 day")
        self.assertEqual(watch.how_long(30), "0 minutes")


if __name__ == "__main__":
    unittest.main()
