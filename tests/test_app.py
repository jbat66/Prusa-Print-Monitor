import json
import os
import threading
import unittest
import tempfile
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from app import Monitor, Handler, normalize, safe_diagnostic


class Response:
    def __init__(self, value): self.value = value
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def read(self): return json.dumps(self.value).encode()


class Tests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'ALERT': 'false', 'CAMERA': 'false'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.monitor = Monitor()

    def test_transition_and_disconnect(self):
        def poll(state):
            with patch.object(self.monitor.opener, 'open', return_value=Response(
                    {'printer': {'state': state}, 'job': {'time_remaining': 600}})):
                self.monitor.poll()
        poll('PRINTING')
        self.assertEqual(self.monitor.snapshot()['event'], 0)
        poll('PRINTING')
        poll('PAUSED')
        self.assertEqual(self.monitor.snapshot()['event'], 1)
        updated = self.monitor.snapshot()['updated']
        with patch.object(self.monitor.opener, 'open', side_effect=OSError('secret')):
            self.monitor.poll()
        self.assertFalse(self.monitor.snapshot()['connected'])
        self.assertEqual(self.monitor.snapshot()['updated'], updated)
        poll('PAUSED')
        self.assertEqual(self.monitor.snapshot()['event'], 1)
        poll('FINISHED')
        self.assertEqual(self.monitor.snapshot()['event'], 2)

    def test_invalid_payload(self):
        for value in (-1, '20', True, float('nan')):
            self.assertIsNone(normalize({'printer': {'state': 'IDLE'},
                'job': {'time_remaining': value}})['remaining'])
        with self.assertRaises((KeyError, ValueError)):
            normalize({'printer': {}})

    def test_http_and_secret_isolation(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.monitor = self.monitor
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            with urllib.request.urlopen(base + '/api/status') as r:
                body = json.load(r)
            self.assertNotIn('API_KEY', body)
            self.assertNotIn('camera_url', body)
            for path in ['/', '/app.js', '/style.css', '/health', '/icon.png', '/favicon.ico']:
                with urllib.request.urlopen(base + path) as r:
                    self.assertEqual(r.status, 200)
            for path in ['/camera', '/alert', '/../app.py']:
                with self.assertRaises(urllib.error.HTTPError):
                    urllib.request.urlopen(base + path)
        finally:
            server.shutdown()
            server.server_close()

    def test_camera_log_redacts_credentials(self):
        url = 'rtsp://maker:secret-password@camera.local/live?token=private-token'
        result = safe_diagnostic(f'Cannot open {url}; secret-password authentication failed', url)
        self.assertNotIn('secret-password', result)
        self.assertNotIn('private-token', result)
        self.assertNotIn('maker', result)

    def test_favicon_has_valid_small_icon_entries(self):
        import struct
        data = Path('assets/favicon.ico').read_bytes()
        self.assertEqual(struct.unpack_from('<HHH', data), (0, 1, 7))
        sizes = []
        for index in range(7):
            width, height, _, _, _, _, length, offset = struct.unpack_from('<BBBBHHII', data, 6 + index * 16)
            size = width or 256
            self.assertEqual(height or 256, size)
            png = data[offset:offset + length]
            self.assertTrue(png.startswith(b'\x89PNG\r\n\x1a\n'))
            self.assertEqual(struct.unpack_from('>II', png, 16), (size, size))
            sizes.append(size)
        self.assertEqual(sizes, [16, 24, 32, 48, 64, 128, 256])

    def test_template_order_and_visibility(self):
        configs = ET.parse('unraid/prusa-print-monitor.xml').getroot().findall('Config')
        variables = [c for c in configs if c.attrib['Type'] == 'Variable']
        self.assertEqual([c.attrib['Target'] for c in variables[:7]],
            ['PRINTER_URL', 'API_USER', 'API_KEY', 'REFRESH_SECONDS',
             'ALERT', 'CAMERA', 'CAMERA_URL'])
        self.assertTrue(all(c.attrib['Display'] == 'always' for c in configs))
        by_target = {c.attrib['Target']: c for c in configs}
        self.assertNotIn('ALERT_SOUND_FILE', by_target)
        self.assertEqual(by_target['CAMERA_URL'].attrib['Mask'], 'false')
        self.assertEqual(by_target['ALERT_REPEAT_SECONDS'].text, '60')
        self.assertEqual(by_target['8085'].attrib['Type'], 'Port')
        self.assertEqual(by_target['/sounds'].attrib['Name'], 'Sound File')
        self.assertTrue(by_target['/sounds'].text.endswith('/redalert.mp3'))

    def test_alert_requires_file(self):
        with patch.dict(os.environ, {'ALERT': 'true'}), patch('app.SOUND_PATH', Path('/missing/sound')):
            with self.assertRaisesRegex(ValueError, '/sounds'): Monitor()

    def test_fixed_sound_path_serves_mp3_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'sounds'
            audio = b'ID3-example-MP3-input'
            source.write_bytes(audio)
            with patch.dict(os.environ, {'ALERT': 'true', 'ALERT_SOUND_FILE': '/ignored'}), patch('app.SOUND_PATH', source):
                monitor = Monitor()
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            server.monitor = monitor
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                with patch('app.subprocess.run') as conversion:
                    url = f'http://127.0.0.1:{server.server_port}/alert'
                    with urllib.request.urlopen(url) as response:
                        self.assertEqual(response.headers['Content-Type'], 'audio/mpeg')
                        self.assertEqual(response.read(), audio)
                    conversion.assert_not_called()
            finally:
                server.shutdown()
                server.server_close()
        self.assertEqual(self.monitor.repeat, 60)
        self.assertEqual(self.monitor.snapshot()['version'], '0.2.7')

    def test_digest_challenge(self):
        import hashlib
        import re
        class Printer(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                auth = self.headers.get('Authorization', '')
                fields = dict(re.findall(r'(\w+)="?([^", ]+)"?', auth))
                h = lambda s: hashlib.md5(s.encode()).hexdigest()
                expected = h(f'{h("maker:printer:test-key")}:nonce:{fields.get("nc")}:'
                             f'{fields.get("cnonce")}:auth:{h("GET:/api/v1/status")}')
                if fields.get('response') != expected:
                    self.send_response(401)
                    self.send_header('WWW-Authenticate',
                        'Digest realm="printer", nonce="nonce", qop="auth", algorithm=MD5')
                    self.end_headers()
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"printer":{"state":"PRINTING"},"job":{"time_remaining":45}}')
        server = ThreadingHTTPServer(('127.0.0.1', 0), Printer)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with patch.dict(os.environ, {'PRINTER_URL': f'http://127.0.0.1:{server.server_port}/api/v1/status',
                                        'API_KEY': 'test-key'}):
                monitor = Monitor()
                monitor.poll()
                self.assertTrue(monitor.snapshot()['connected'])
                self.assertEqual(monitor.snapshot()['remaining'], 45)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__': unittest.main()
