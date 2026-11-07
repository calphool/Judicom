"""A real bash on a pseudo-terminal, for the maintenance shell (judicom/maintenance.py).  No pygame: judicom/shell_view.py draws it.

    shell = Shell(log=log)      # bash starts; pyte keeps track of what its screen would look like
    shell.poll()                # call often: reads what bash wrote; False once bash has ended
    shell.send(b"ls\r")         # what the keys type
    shell.screen                # the pyte.Screen to draw;  shell.dirty: it has changed since the view last drew it
    shell.close()               # hangs up, as when an SSH session drops

Needs:  sudo apt install python3-pyte
"""
import fcntl
import os
import pty
import pwd
import signal
import struct
import termios
import threading
import time

import pyte

from . import config

MAX_READ = 4096                 # a frame's worth: a command that pours out text must not hold up the phone's main loop
HANG_UP_SECONDS = 2.0           # what bash gets to end after the hang-up


def environment():
    """Not the phone program's: bash gets what a login gets, and none of the screen settings."""
    user = pwd.getpwuid(os.getuid())
    return {"HOME": user.pw_dir, "USER": user.pw_name, "LOGNAME": user.pw_name, "SHELL": "/bin/bash", "TERM": "linux",
            "LANG": os.environ.get("LANG", "C.UTF-8"), "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"}


def _reap(pid):
    """Waits for a bash that was hung up on, in the background: the main loop must not wait, and no dead process is left behind."""
    try:
        for _ in range(int(HANG_UP_SECONDS / 0.1)):
            if os.waitpid(pid, os.WNOHANG)[0]:
                return
            time.sleep(0.1)
        os.killpg(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    except OSError:
        pass


class Shell:
    def __init__(self, columns=config.SHELL_COLUMNS, rows=config.SHELL_ROWS, log=None, command=("/bin/bash", "-l")):
        self.log = log or (lambda msg: None)
        self.screen = pyte.Screen(columns, rows)
        self.screen.write_process_input = lambda text: self.send(text.encode())       # programs that ask the terminal something
        self.stream = pyte.ByteStream(self.screen)
        self.dirty = True
        env = environment()
        self.pid, self.fd = pty.fork()
        if self.pid == 0:                                # the child: only as far as exec, and never back into the phone program
            try:
                fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
                signal.pthread_sigmask(signal.SIG_SETMASK, [])
                signal.signal(signal.SIGPIPE, signal.SIG_DFL)            # Python ignores these two, and bash would inherit that
                signal.signal(signal.SIGXFSZ, signal.SIG_DFL)
                os.closerange(3, 65536)                  # no file of the phone program goes with it
                os.chdir(env["HOME"])
                os.execve(command[0], list(command), env)
            finally:
                os._exit(127)
        os.set_blocking(self.fd, False)

    @property
    def alive(self):
        return self.fd is not None

    def poll(self):
        if self.fd is None:
            return False
        try:
            data = os.read(self.fd, MAX_READ)
            if not data:
                self.close()
                return False
            self.stream.feed(data)
            self.dirty = True
        except BlockingIOError:
            pass
        except OSError:                                  # EIO: nothing has the terminal open any more
            self.close()
            return False
        except Exception as exc:                         # noqa: BLE001 - whatever pyte makes of the text, the phone goes on
            self.log("(the shell's screen failed: %r)" % exc)
            self.close()
            return False
        try:
            if os.waitpid(self.pid, os.WNOHANG)[0]:      # bash has gone, even if something it left running keeps the terminal
                self.pid = None
                self.close()
                return False
        except OSError:
            self.pid = None
            self.close()
            return False
        return True

    def send(self, data):
        if self.fd is None:
            return
        try:
            os.write(self.fd, data)
        except OSError:                                  # full, or bash has just gone: poll() finds out
            pass

    def close(self):
        if self.fd is None:
            return
        fd, self.fd = self.fd, None
        os.close(fd)                                     # the hang-up
        if self.pid:
            threading.Thread(target=_reap, args=(self.pid,), name="shell hang-up", daemon=True).start()
            self.pid = None
