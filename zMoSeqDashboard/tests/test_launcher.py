"""Standard-library checks for local file discovery and HTTP endpoints."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import urlopen, Request
from urllib.error import HTTPError

spec = importlib.util.spec_from_file_location('launcher', Path(__file__).resolve().parents[1] / 'launch.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class LauncherTests(unittest.TestCase):
    def test_catalog_and_http(self):
        original_root, original_raw = app.ROOT, app.RAW
        with tempfile.TemporaryDirectory() as temporary:
            app.ROOT = Path(temporary)
            app.RAW = app.ROOT / 'data_MoSeq_raw'
            app.RAW.mkdir()
            raw = app.RAW / 'example.txt'
            content = b'subject\tgroup\tsyllable\tusage\ttreat\na\t0\t0\t0.5\tVehicle\n'
            raw.write_bytes(content)
            (app.RAW / 'example.moseq-notes.json').write_text('{}')
            (app.ROOT / 'index.html').write_text('<h1>test app</h1>')
            server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = 'http://127.0.0.1:' + str(server.server_address[1])
            try:
                self.assertEqual(app.make_catalog(), 1)
                self.assertEqual(raw.read_bytes(), content)
                self.assertIn('example.txt', (app.ROOT / 'catalog.js').read_text())
                with urlopen(base + '/api/files') as response:
                    self.assertEqual(json.load(response)['files'], ['example.txt'])
                with urlopen(base + '/api/data?name=example.txt') as response:
                    self.assertEqual(response.read(), content)
                for suffix in ['/api/data?name=../index.html', '/api/data?name=example.moseq-notes.json', '/data_MoSeq_raw/']:
                    with self.assertRaises(HTTPError):
                        urlopen(base + suffix)
                payload = {'app': 'MoSeq Dashboard', 'version': '0.1', 'dataset': {'name': 'example.txt', 'text': content.decode()}, 'settings': {'selected': ['0']}}
                def save(value, origin=base):
                    return urlopen(Request(base + '/api/session', data=json.dumps(value).encode(), headers={'Content-Type': 'application/json', 'Origin': origin}))
                with save(payload) as response:
                    self.assertEqual(json.load(response)['saved'], 'example_session.json')
                with urlopen(base + '/api/session?name=example.txt') as response:
                    self.assertEqual(json.load(response), payload)
                payload['settings']['workspace'] = 'heatmaps'
                with save(payload):
                    pass
                self.assertTrue((app.RAW / 'example_session.previous.json').is_file())
                self.assertEqual(raw.read_bytes(), content)
                with self.assertRaises(HTTPError) as blocked:
                    save(payload, 'http://untrusted.example')
                self.assertEqual(blocked.exception.code, 403)
                with self.assertRaises(HTTPError) as blocked_close:
                    urlopen(Request(base + '/api/shutdown', data=b'{}', headers={'Content-Type': 'application/json', 'Origin': 'http://untrusted.example'}))
                self.assertEqual(blocked_close.exception.code, 403)
                payload['dataset']['text'] += '\nchanged'
                with self.assertRaises(HTTPError) as changed:
                    save(payload)
                self.assertEqual(changed.exception.code, 409)
                (app.RAW / 'new.csv').write_text('hello')
                with urlopen(base + '/api/files') as response:
                    self.assertIn('new.csv', json.load(response)['files'])
            finally:
                server.shutdown()
                server.server_close()
                worker.join()
                app.ROOT, app.RAW = original_root, original_raw


if __name__ == '__main__':
    unittest.main()
