import io
import os
import json
import threading
import unittest
import urllib.request
from unittest.mock import patch
from app import Monitor, MonitorServer, camera_command


class CameraTests(unittest.TestCase):
    def test_timeout_options_match_camera_protocol(self):
        rtsp = camera_command('rtsp://camera.local/live')
        self.assertNotIn('-rw_timeout', rtsp)
        self.assertIn('-timeout', rtsp[:rtsp.index('-i')])
        self.assertEqual(rtsp[rtsp.index('-rtsp_transport') + 1], 'tcp')
        for scheme in ('http', 'https'):
            args = camera_command(f'{scheme}://camera.local/live')
            self.assertIn('-rw_timeout', args[:args.index('-i')])
            self.assertNotIn('-rtsp_transport', args)

    def test_camera_failure_is_logged_and_reported_to_browser(self):
        with patch.dict(os.environ, {'ALERT': 'false', 'CAMERA': 'true',
                                    'CAMERA_URL': 'rtsp://user:secret@camera.local/live'}):
            monitor = Monitor()
        server = MonitorServer(('127.0.0.1', 0), monitor)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        class Process:
            stdout = io.BytesIO(b'')
            stderr = io.BytesIO(b'401 Unauthorized rtsp://user:secret@camera.local/live\n')
            def poll(self): return 1
            def wait(self, **kwargs): return 1
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            with self.assertLogs('Prusa-Print-Monitor.log', level='INFO') as logs:
                with patch('app.subprocess.Popen', return_value=Process()):
                    with urllib.request.urlopen(base + '/camera?viewer=test') as response:
                        response.read()
                    with urllib.request.urlopen(base + '/api/camera/status?viewer=test') as response:
                        status = json.load(response)
            self.assertEqual(status['state'], 'error')
            self.assertIn('UNRAID container logs', status['message'])
            self.assertIn('Camera stream ended', '\n'.join(logs.output))
            self.assertNotIn('secret', '\n'.join(logs.output))
        finally:
            server.shutdown()
            server.server_close()
