"""Exercise real Unix signals, including a camera child blocked on input."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request


@unittest.skipIf(os.name == 'nt', 'Linux container signal semantics')
class ShutdownTests(unittest.TestCase):
    def launch(self, extra=None):
        env = dict(os.environ, ALERT='false', CAMERA='false',
                   PRINTER_URL='http://127.0.0.1:1/api/v1/status', REFRESH_SECONDS='60')
        env.update(extra or {})
        process = subprocess.Popen([sys.executable, '-u', 'app.py'], env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.cleanup, process)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if process.poll() is not None:
                self.fail(f'Server exited early: {process.communicate()}')
            try:
                with urllib.request.urlopen('http://127.0.0.1:8085/api/status', timeout=.2) as response:
                    self.assertEqual(json.load(response)['version'], '0.2.3')
                    return process
            except OSError:
                time.sleep(.05)
        self.fail('Server did not start')

    @staticmethod
    def cleanup(process):
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=3)

    def test_sigterm_and_sigint_exit_cleanly(self):
        for sig in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=sig):
                process = self.launch()
                process.send_signal(sig)
                output, error = process.communicate(timeout=3)
                self.assertEqual(process.returncode, 0, error.decode())
                self.assertIn(b'stopped cleanly', output)

    def test_sigterm_stops_blocked_camera_child(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'ffmpeg'
            child_pid = Path(directory) / 'camera.pid'
            executable.write_text(f'#!{sys.executable}\n'
                'import os, time\nfrom pathlib import Path\n'
                'Path(os.environ["CAMERA_PID_FILE"]).write_text(str(os.getpid()))\n'
                'while True: time.sleep(1)\n')
            executable.chmod(0o755)
            process = self.launch(dict(CAMERA='true', CAMERA_URL='rtsp://example.invalid/live',
                CAMERA_PID_FILE=str(child_pid), PATH=directory + os.pathsep + os.environ['PATH']))
            response = urllib.request.urlopen('http://127.0.0.1:8085/camera', timeout=2)
            try:
                deadline = time.monotonic() + 2
                while not child_pid.exists() and time.monotonic() < deadline:
                    time.sleep(.05)
                self.assertTrue(child_pid.exists())
                pid = int(child_pid.read_text())
                process.send_signal(signal.SIGTERM)
                _, error = process.communicate(timeout=4)
                self.assertEqual(process.returncode, 0, error.decode())
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)
            finally:
                response.close()
