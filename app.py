"""Small LAN-only PrusaLink monitor. Credentials never leave this process."""
import json
import math
import os
import signal
from pathlib import Path
import subprocess
import threading
import time
import urllib.request
from urllib.parse import urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).parent
VERSION = (ROOT / 'VERSION').read_text().strip()
PORT = 8085
SOUND_PATH = Path('/sounds')


def seconds(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def normalize(data):
    state = data['printer']['state']
    if not isinstance(state, str) or not state.strip():
        raise ValueError('Missing printer state')
    job = data.get('job') or {}
    return dict(state=state.upper(), remaining=seconds(job.get('time_remaining')),
                filament=seconds(job.get('filament_change_in')))


class Monitor:
    def __init__(self):
        self.refresh = int(os.getenv('REFRESH_SECONDS', '60'))
        self.repeat = int(os.getenv('ALERT_REPEAT_SECONDS', '60'))
        self.timeout = int(os.getenv('REQUEST_TIMEOUT_SECONDS', '10'))
        if min(self.refresh, self.repeat, self.timeout) < 1:
            raise ValueError('Intervals must be positive integers')
        self.url = os.getenv('PRINTER_URL', 'http://X.X.X.X/api/v1/status')
        if urlparse(self.url).scheme not in ('http', 'https'):
            raise ValueError('PRINTER_URL must use HTTP or HTTPS')
        self.sound = SOUND_PATH
        self.alert = os.getenv('ALERT', 'false').lower() == 'true'
        self.camera = os.getenv('CAMERA', 'false').lower() == 'true'
        self.camera_url = os.getenv('CAMERA_URL', 'rtsp://x.x.x.x/live')
        if self.alert and (not self.sound.is_file() or not os.access(self.sound, os.R_OK)):
            raise ValueError('ALERT=true requires a readable sound file mounted at /sounds')
        if self.camera and urlparse(self.camera_url).scheme not in ('rtsp', 'http', 'https'):
            raise ValueError('CAMERA_URL must use RTSP, HTTP or HTTPS')
        passwords = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        passwords.add_password(None, self.url, os.getenv('API_USER', 'maker'),
                               os.getenv('API_KEY', 'PUT-KEY-HERE'))
        self.opener = urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(passwords))
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.data = dict(state='UNKNOWN', remaining=None, filament=None,
                         connected=False, updated=None, attempted=None, event=0)

    def poll(self):
        try:
            with self.opener.open(self.url, timeout=self.timeout) as response:
                result = normalize(json.load(response))
            with self.lock:
                event = self.data['event'] + int(self.data['updated'] is not None and
                                                result['state'] != self.data['state'])
                self.data.update(result, connected=True, updated=time.time(),
                                 attempted=time.time(), event=event)
        except Exception:
            # Never expose upstream URLs, credentials or response bodies.
            with self.lock:
                self.data.update(connected=False, attempted=time.time())

    def run(self):
        while not self.stop.is_set():
            self.poll()
            self.stop.wait(self.refresh)

    def snapshot(self):
        with self.lock:
            return dict(self.data, refresh=self.refresh, repeat=self.repeat,
                        alert=self.alert, camera=self.camera, server_time=time.time(), version=VERSION)

def stop_camera(process):
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=1)


class MonitorServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, monitor):
        super().__init__(address, Handler)
        self.monitor = monitor
        self.timeout = 0.25
        self.camera_slots = threading.BoundedSemaphore(4)
        self.camera_lock = threading.Lock()
        self.cameras = set()

    def start_camera(self, args):
        with self.camera_lock:
            if self.monitor.stop.is_set():
                raise OSError('Server is stopping')
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self.cameras.add(process)
            return process

    def close_cameras(self):
        with self.camera_lock:
            cameras = list(self.cameras)
        # Signal every camera before waiting for any of them.
        for process in cameras:
            if process.poll() is None:
                process.terminate()
        for process in cameras:
            stop_camera(process)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, body, content_type, status=200):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/api/status':
            self.send(json.dumps(self.server.monitor.snapshot()).encode(), 'application/json')
        elif path == '/health':
            self.send(b'ok', 'text/plain')
        elif path == '/alert' and self.server.monitor.alert:
            try:
                self.send(self.server.monitor.sound.read_bytes(), 'audio/mpeg')
            except OSError:
                self.send(b'Unable to read the MP3 file mounted at /sounds', 'text/plain', 503)
        elif path == '/camera' and self.server.monitor.camera:
            self.stream_camera()
        elif path in ('/', '/app.js', '/style.css'):
            file = ROOT / 'static' / ('index.html' if path == '/' else path[1:])
            self.send(file.read_bytes(), {'/': 'text/html; charset=utf-8',
                      '/app.js': 'text/javascript', '/style.css': 'text/css'}[path])
        else:
            self.send(b'Not found', 'text/plain', 404)

    def stream_camera(self):
        if not self.server.camera_slots.acquire(blocking=False):
            self.send(b'Camera viewer limit reached', 'text/plain', 503)
            return
        process = None
        try:
            url = self.server.monitor.camera_url
            args = ['ffmpeg', '-nostdin', '-loglevel', 'error', '-rw_timeout', '10000000']
            if urlparse(url).scheme == 'rtsp':
                args += ['-rtsp_transport', 'tcp']
            process = self.server.start_camera(args + ['-i', url, '-an', '-vf',
                'fps=3,scale=960:-2', '-f', 'mpjpeg', '-boundary_tag', 'frame', 'pipe:1'])
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            while chunk := process.stdout.read1(65536):
                self.wfile.write(chunk)
                self.wfile.flush()
        except (OSError, BrokenPipeError):
            pass
        finally:
            if process:
                stop_camera(process)
                process.stdout.close()
                with self.server.camera_lock:
                    self.server.cameras.discard(process)
            self.server.camera_slots.release()


def main():
    monitor = Monitor()
    server = MonitorServer(('0.0.0.0', PORT), monitor)
    # Keep signal handlers small. handle_request has a bounded timeout, so
    # shutdown happens in the main loop without socketserver.shutdown deadlocks.
    def request_stop(signum, frame):
        monitor.stop.set()
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    threading.Thread(target=monitor.run, daemon=True).start()
    print(f'Prusa Print Monitor {VERSION} listening on port {PORT}', flush=True)
    try:
        while not monitor.stop.is_set():
            server.handle_request()
    finally:
        monitor.stop.set()
        server.close_cameras()
        server.server_close()
        print('Prusa Print Monitor stopped cleanly', flush=True)


if __name__ == '__main__':
    main()
