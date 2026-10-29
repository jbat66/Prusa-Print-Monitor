"""Small LAN-only PrusaLink monitor. Credentials never leave this process."""
import json
import logging
import math
import os
import signal
import re
import sys
from pathlib import Path
import subprocess
import threading
import time
import urllib.request
from urllib.parse import urlparse, parse_qs, unquote
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).parent
VERSION = (ROOT / 'VERSION').read_text().strip()
PORT = 8085
SOUND_PATH = Path('/sounds')
LOG = logging.getLogger('Prusa-Print-Monitor.log')


def safe_diagnostic(message, camera_url=''):
    text = str(message)
    if camera_url:
        text = text.replace(camera_url, '[camera URL]')
    text = re.sub(r'(?:rtsp|https?)://[^\s\]\'\"]+', '[URL redacted]', text)
    parsed = urlparse(camera_url)
    for secret in (parsed.username, parsed.password, os.getenv('API_KEY')):
        if secret:
            text = text.replace(secret, '[redacted]').replace(unquote(secret), '[redacted]')
    return text[:1500]


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
        self.default_layout = os.getenv('DEFAULT_LAYOUT', 'desktop').strip().lower()
        if self.default_layout not in ('desktop', 'compact', 'mobile', 'large'):
            raise ValueError('DEFAULT_LAYOUT must be desktop, compact, mobile or large')
        if min(self.refresh, self.repeat, self.timeout) < 1:
            raise ValueError('Intervals must be positive integers')
        self.url = os.getenv('PRINTER_URL', 'http://X.X.X.X/api/v1/status')
        if urlparse(self.url).scheme not in ('http', 'https'):
            raise ValueError('PRINTER_URL must use HTTP or HTTPS')
        # Old file mounts still play; new folder mounts select by basename.
        # Host paths cannot be accessed inside Docker, so the template's host
        # filename is resolved under the mounted /sounds directory.
        self.sound = SOUND_PATH if SOUND_PATH.is_file() else SOUND_PATH / Path(
            os.getenv('SOUND_FILE', 'AlarmSoundEffect.mp3')).name
        self.alert = os.getenv('ALERT', 'false').lower() == 'true'
        self.camera = os.getenv('CAMERA', 'false').lower() == 'true'
        self.camera_url = os.getenv('CAMERA_URL', 'rtsp://x.x.x.x/live')
        if self.alert and (not self.sound.is_file() or not os.access(self.sound, os.R_OK)):
            raise ValueError('ALERT=true requires a readable selected MP3 under /sounds; check Sound File and Sounds Folder')
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
                previous = self.data.copy()
                event = self.data['event'] + int(self.data['updated'] is not None and
                                                result['state'] != self.data['state'])
                self.data.update(result, connected=True, updated=time.time(),
                                 attempted=time.time(), event=event)
            if not previous['connected']:
                LOG.info('Printer connected; state=%s', result['state'])
            elif previous['state'] != result['state']:
                LOG.info('Printer state changed: %s -> %s', previous['state'], result['state'])
        except Exception as error:
            # Never expose upstream URLs, credentials or response bodies.
            with self.lock:
                report = self.data['connected'] or self.data['attempted'] is None
                self.data.update(connected=False, attempted=time.time())
            if report:
                LOG.warning('Printer request failed (%s); check printer address, credentials and network', type(error).__name__)

    def run(self):
        while not self.stop.is_set():
            self.poll()
            self.stop.wait(self.refresh)

    def snapshot(self):
        with self.lock:
            return dict(self.data, refresh=self.refresh, repeat=self.repeat,
                        alert=self.alert, camera=self.camera, server_time=time.time(), version=VERSION,
                        default_layout=self.default_layout)

def stop_camera(process):
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=1)


def camera_command(url):
    args = ['ffmpeg', '-nostdin', '-loglevel', 'error']
    if urlparse(url).scheme == 'rtsp':
        # RTSP is a demuxer and does not consume the HTTP rw_timeout option.
        args += ['-rtsp_transport', 'tcp', '-timeout', '10000000']
    else:
        args += ['-rw_timeout', '10000000']
    return args + ['-i', url, '-an', '-vf', 'fps=3,scale=960:-2',
        '-c:v', 'mjpeg', '-threads', '1', '-q:v', '5',
        '-f', 'mpjpeg', '-boundary_tag', 'frame', 'pipe:1']


class MonitorServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, monitor):
        super().__init__(address, Handler)
        self.monitor = monitor
        self.timeout = 0.25
        self.camera_slots = threading.BoundedSemaphore(4)
        self.camera_lock = threading.Lock()
        self.cameras = set()
        self.camera_states = {}

    def camera_state(self, viewer, state=None, message=None):
        with self.camera_lock:
            if state:
                self.camera_states[viewer] = dict(state=state, message=message)
                if len(self.camera_states) > 128:
                    del self.camera_states[next(iter(self.camera_states))]
            return self.camera_states.get(viewer, dict(state='connecting', message='Connecting camera…')).copy()

    def log_camera_errors(self, process):
        for line in process.stderr:
            detail = safe_diagnostic(line.decode('utf-8', errors='replace').strip(), self.monitor.camera_url)
            if detail:
                LOG.warning('Camera FFmpeg: %s', detail)

    def start_camera(self, args):
        with self.camera_lock:
            if self.monitor.stop.is_set():
                raise OSError('Server is stopping')
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.cameras.add(process)
            threading.Thread(target=self.log_camera_errors, args=(process,), daemon=True).start()
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
        target = urlparse(self.path)
        path = target.path
        viewer = parse_qs(target.query).get('viewer', ['default'])[0][:64]
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
            self.stream_camera(viewer)
        elif path == '/api/camera/status' and self.server.monitor.camera:
            self.send(json.dumps(self.server.camera_state(viewer)).encode(), 'application/json')
        elif path in ('/icon.png', '/app-icon.png'):
            self.send((ROOT / 'assets' / 'app-icon.png').read_bytes(), 'image/png')
        elif path == '/favicon.ico':
            self.send((ROOT / 'assets' / 'favicon.ico').read_bytes(), 'image/x-icon')
        elif path in ('/', '/app.js', '/style.css'):
            file = ROOT / 'static' / ('index.html' if path == '/' else path[1:])
            self.send(file.read_bytes(), {'/': 'text/html; charset=utf-8',
                      '/app.js': 'text/javascript', '/style.css': 'text/css'}[path])
        else:
            self.send(b'Not found', 'text/plain', 404)

    def stream_camera(self, viewer='default'):
        if not self.server.camera_slots.acquire(blocking=False):
            self.server.camera_state(viewer, 'error', 'Camera viewer limit reached. Close another camera view and retry.')
            LOG.warning('Camera viewer limit reached')
            self.send(b'Camera viewer limit reached', 'text/plain', 503)
            return
        process = None
        finished = threading.Event()
        last_data = [time.monotonic()]
        live = False
        failed = False
        def watchdog():
            while not finished.wait(1):
                if time.monotonic() - last_data[0] > 15:
                    self.server.camera_state(viewer, 'error', 'Camera timed out. Check UNRAID container logs and CAMERA_URL.')
                    LOG.error('Camera timed out: no complete video frame for 15 seconds')
                    stop_camera(process)
                    return
        try:
            self.server.camera_state(viewer, 'connecting', 'Connecting camera…')
            LOG.info('Camera connection requested (%s); URL credentials are redacted', urlparse(self.server.monitor.camera_url).scheme)
            url = self.server.monitor.camera_url
            process = self.server.start_camera(camera_command(url))
            threading.Thread(target=watchdog, daemon=True).start()
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            tail = b''
            while chunk := process.stdout.read1(65536):
                if b'\xff\xd9' in tail + chunk:
                    last_data[0] = time.monotonic()
                    if not live:
                        live = True
                        self.server.camera_state(viewer, 'live', 'Live camera')
                        LOG.info('Camera video frames received; streaming to browser')
                tail = chunk[-1:]
                self.wfile.write(chunk)
                self.wfile.flush()
            failed = not self.server.monitor.stop.is_set()
            if failed:
                self.server.camera_state(viewer, 'error', 'Camera stream ended. Check UNRAID container logs; disable and enable the camera to retry.')
                try:
                    exit_code = process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    exit_code = 'still running; stopping worker'
                LOG.warning('Camera stream ended; FFmpeg exit code=%s', exit_code)
        except (BrokenPipeError, ConnectionResetError):
            LOG.info('Camera viewer disconnected')
        except OSError as error:
            failed = True
            self.server.camera_state(viewer, 'error', 'Camera unavailable. Check UNRAID container logs.')
            LOG.error('Camera failed: %s', safe_diagnostic(error, self.server.monitor.camera_url))
        finally:
            finished.set()
            if process:
                stop_camera(process)
                process.stdout.close()
                with self.server.camera_lock:
                    self.server.cameras.discard(process)
            if not failed and self.server.camera_state(viewer)['state'] != 'error':
                self.server.camera_state(viewer, 'stopped', 'Camera stopped')
            LOG.info('Camera session closed')
            self.server.camera_slots.release()


def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    monitor = Monitor()
    server = MonitorServer(('0.0.0.0', PORT), monitor)
    # Keep signal handlers small. handle_request has a bounded timeout, so
    # shutdown happens in the main loop without socketserver.shutdown deadlocks.
    def request_stop(signum, frame):
        monitor.stop.set()
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    threading.Thread(target=monitor.run, daemon=True).start()
    LOG.info('Prusa Print Monitor %s listening on port %s; alerts=%s camera=%s', VERSION, PORT, monitor.alert, monitor.camera)
    try:
        while not monitor.stop.is_set():
            server.handle_request()
    finally:
        monitor.stop.set()
        server.close_cameras()
        server.server_close()
        LOG.info('Prusa Print Monitor stopped cleanly')


if __name__ == '__main__':
    main()
